/*
	Copyright 2019 Benjamin Vedder	benjamin@vedder.se

	This file is part of the VESC firmware.

	The VESC firmware is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The VESC firmware is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    */

/*
 * Atlas Autoware ATLAS-DRV-1 (car v2 drive board). Derived from hwconf/trampa/hd/hw_hd60.c
 * (Copyright 2019 Benjamin Vedder, GPL-3.0-or-later). See hw_atlas_drv1.h for what differs from
 * the HD60. Everything below "ATLAS supervisor" is new.
 */

#include "hw.h"

#include <math.h>
#include <string.h>

#include "ch.h"
#include "hal.h"
#include "stm32f4xx_conf.h"
#include "utils_math.h"
#include "drv8323s.h"
#include "terminal.h"
#include "commands.h"
#include "mc_interface.h"
#include "mcpwm_foc.h"

// Variables
static volatile bool i2c_running = false;

// I2C configuration
static const I2CConfig i2cfg = {
		OPMODE_I2C,
		100000,
		STD_DUTY_CYCLE
};

/* ------------------------------------------------------------------------------------------ */
/* ATLAS supervisor                                                                            */
/* ------------------------------------------------------------------------------------------ */

// Timing (ms)
#define SUP_PERIOD_MS				5		// supervisor loop
#define PRECHARGE_CHECK_MS			10		// time before the "is the bus shorted" check
#define PRECHARGE_MAX_MS			400		// the bus must have settled by then
#define PRECHARGE_RETRY_GAP_MS		15000	// between manual retries (resistor pulse rating)
#define DRV_WAKE_MS					2		// DRV8323 wake-up before SPI works (datasheet ~1 ms)
#define DRV_CHECK_MS				250		// read back the CSA gain this often
#define DRV_HOLD_AFTER_RESTORE_MS	500		// keep the motor released after a restore
#define JETSON_PRESS_AFTER_MS		5000	// press the power button if the module is still off
#define JETSON_PRESS_MS				500
#define JETSON_PRESS_RETRY_MS		20000
#define JETSON_ON_CONFIRM_MS		1000	// OS_HALTED low this long = module running
#define JETSON_HALT_CONFIRM_MS		3000	// OS_HALTED high this long after running = module halted
#define JETSON_SHUTDOWN_PRESS_MS	1000	// power-key event length for a shutdown request
#define JETSON_SHUTDOWN_WAIT_MS		60000	// then wait this long for it to halt

typedef enum {
	PWR_WAIT_ADC = 0,
	PWR_PRECHARGE,
	PWR_ON,
	PWR_FAULT_SHORT,		// the bus did not rise: something on VM is shorted
	PWR_FAULT_TIMEOUT,		// the bus did not settle in time
	PWR_MAIN_OFF,			// opened on purpose (terminal)
	PWR_SHUTTING_DOWN,
} atlas_pwr_state;

static const char *pwr_state_names[] = {
		"waiting for ADC", "precharging", "on", "FAULT: bus shorted (did not rise)",
		"FAULT: bus did not settle", "main switch off (terminal)", "shutting down"
};

static THD_WORKING_AREA(sup_thread_wa, 2048);
static volatile atlas_pwr_state m_pwr_state = PWR_WAIT_ADC;
static volatile bool m_precharge_request = true;		// run once at boot
static volatile systime_t m_last_precharge_time = 0;
static volatile float m_precharge_v_end = 0.0;

static volatile bool m_drv_cfg_ok = false;			// CSA gain read back as 40 V/V since the last wake
static volatile bool m_dccal_suspect = false;		// current offsets measured while the DRV slept
static volatile int m_drv_restores = 0;
static volatile int m_drv_restore_failures = 0;
static volatile int m_estop_openings = 0;

static volatile bool m_jetson_seen_on = false;
static volatile int m_jetson_presses = 0;
static volatile bool m_auto_off = true;				// turn the car off when the Jetson halts
static volatile bool m_poweroff_request = false;	// from the terminal, done by the supervisor
static volatile bool m_poweroff_active = false;

static mutex_t m_poweroff_mutex;

static THD_FUNCTION(sup_thread, arg);
static bool atlas_precharge(void);
static void atlas_power_off(bool ask_jetson);
static void atlas_hold_motor(int ms);
static bool atlas_drv_restore(void);
static bool atlas_drv_gain_ok(void);

// Terminal
static void terminal_status(int argc, const char **argv);
static void terminal_precharge(int argc, const char **argv);
static void terminal_main_off(int argc, const char **argv);
static void terminal_brain(int argc, const char **argv);
static void terminal_autooff(int argc, const char **argv);
static void terminal_poweroff(int argc, const char **argv);
static void terminal_button_test(int argc, const char **argv);

static float avg_input_voltage(void) {
	float sum = 0.0;
	for (int i = 0;i < 8;i++) {
		sum += GET_INPUT_VOLTAGE();
		chThdSleepMicroseconds(250);
	}
	return sum / 8.0;
}

float hw_atlas_get_bus_current(void) {
	return ADC_VOLTS(ADC_IND_EXT) / ATLAS_IMON_V_PER_A;
}

// Motor released and user commands ignored for the next ms milliseconds. Only valid once
// mc_interface is running (its first DC calibration done).
static void atlas_hold_motor(int ms) {
	if (!mcpwm_foc_is_dccal_done()) {
		return;
	}
	mc_interface_ignore_input_both(ms);
	mc_interface_release_motor_override_both();
}

// Precharge the bus through the 2 x 22 Ohm resistors (tau about 16 ms), then close the main FETs.
// The resistors take one charging pulse, not a short on VM (13 W each), so a bus that is still
// under 4 V after 10 ms is left off at once (sim/precharge.py).
static bool atlas_precharge(void) {
	m_pwr_state = PWR_PRECHARGE;
	m_last_precharge_time = chVTGetSystemTimeX();

	palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
	palSetPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	chThdSleepMilliseconds(PRECHARGE_CHECK_MS);

	float v = avg_input_voltage();
	if (v < 4.0) {
		palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
		m_precharge_v_end = v;
		m_pwr_state = PWR_FAULT_SHORT;
		commands_printf("ATLAS: precharge stopped, bus only %.2f V after %d ms (short on VM?)",
				(double)v, PRECHARGE_CHECK_MS);
		return false;
	}

	bool settled = false;
	float last = v;
	for (int t = PRECHARGE_CHECK_MS;t < PRECHARGE_MAX_MS;t += 20) {
		chThdSleepMilliseconds(20);
		v = avg_input_voltage();
		if (v > 9.0 && fabsf(v - last) < 0.15) {
			settled = true;
			break;
		}
		last = v;
	}

	m_precharge_v_end = v;
	if (!settled) {
		palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
		m_pwr_state = PWR_FAULT_TIMEOUT;
		commands_printf("ATLAS: precharge stopped, bus at %.2f V did not settle", (double)v);
		return false;
	}

	palSetPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
	chThdSleepMilliseconds(20);
	palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	m_pwr_state = PWR_ON;
	return true;
}

// DRV8323 settings as drv8323s_init() and mc_interface_init() leave them.
static bool atlas_drv_restore(void) {
	const volatile mc_configuration *conf = mc_interface_get_configuration();

	if (atlas_drv_gain_ok()) {
		return true;	// awake and still configured (e.g. the first check after boot)
	}

	// The DRV8323 came back with its defaults (20 V/V): whatever current offsets were measured
	// since it last woke up belong to the other gain or to a sleeping chip.
	m_dccal_suspect = true;

	drv8323s_write_reg(5, 0b0000000111010000);
	drv8323s_set_current_amp_gain(CURRENT_AMP_GAIN);
	drv8323s_set_oc_mode(conf->m_drv8301_oc_mode);
	drv8323s_set_oc_adj(conf->m_drv8301_oc_adj);

	m_drv_restores++;
	bool ok = atlas_drv_gain_ok();
	if (!ok) {
		m_drv_restore_failures++;
	}
	return ok;
}

// CSA_GAIN is bits 7:6 of register 6; 0b11 is 40 V/V.
static bool atlas_drv_gain_ok(void) {
	unsigned int reg = drv8323s_read_reg(6);
	if (reg == 0xFFFF || reg == 0x0000) {
		return false;	// SDO pulled up, or nothing answered
	}
	return ((reg >> 6) & 0x03) == 0x03;
}

// The whole power-off: motor off, Jetson asked to shut down (optional), brain board off, main
// switch open, latch cleared. Does not return while the board still has power.
static void atlas_power_off(bool ask_jetson) {
	chMtxLock(&m_poweroff_mutex);
	m_poweroff_active = true;
	m_pwr_state = PWR_SHUTTING_DOWN;

	DISABLE_GATE();
	atlas_hold_motor(100000);

	if (ask_jetson && !palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN)) {
		palClearPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
		chThdSleepMilliseconds(JETSON_SHUTDOWN_PRESS_MS);
		palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);

		int halted_ms = 0;
		for (int t = 0;t < JETSON_SHUTDOWN_WAIT_MS && halted_ms < 500;t += 50) {
			chThdSleepMilliseconds(50);
			DISABLE_GATE();
			if (palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN)) {
				halted_ms += 50;
			} else {
				halted_ms = 0;
			}
		}
	}

	palClearPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
	chThdSleepMilliseconds(100);
	palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
	palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	chThdSleepMilliseconds(10);

	for (;;) {
		palSetPad(HW_KILL_GPIO, HW_KILL_PIN);	// latch cleared: +5V, +3V3 and this MCU go down
		DISABLE_GATE();
		chThdSleepMilliseconds(100);			// still here while the button is held down
	}
}

// VESC's shutdown thread calls this (HW_SHUTDOWN_HOLD_OFF) on a button press, after saving its
// backup data. It blocks until the board is off.
void hw_atlas_power_off_from_button(void) {
	atlas_power_off(true);
}

static THD_FUNCTION(sup_thread, arg) {
	(void)arg;
	chRegSetThreadName("Atlas supervisor");

	// The ADC starts inside mc_interface_init(), after hw_init_gpio(). Vrefint reads about
	// 1500 counts once the DMA is running.
	systime_t t_start = chVTGetSystemTimeX();
	while (ADC_Value[ADC_IND_VREFINT] < 1000 && ST2MS(chVTTimeElapsedSinceX(t_start)) < 3000) {
		chThdSleepMilliseconds(5);
	}
	chThdSleepMilliseconds(20);

	systime_t t_boot = chVTGetSystemTimeX();
	bool drv_awake_last = false;
	systime_t t_drv_awake = t_boot;
	systime_t t_drv_check = t_boot;
	systime_t t_press_start = 0;
	bool pressing = false;
	systime_t t_last_press = 0;
	int jetson_on_ms = 0;
	int jetson_halted_ms = 0;

	for (;;) {
		systime_t now = chVTGetSystemTimeX();

		// ---- main switch
		if (m_precharge_request) {
			m_precharge_request = false;
			atlas_precharge();
		}

		// ---- E-stop and DRV8323 configuration
		bool estop_ok = IS_ESTOP_OK();
		bool drv_awake = estop_ok && IS_GATE_ENABLED();

		if (!estop_ok) {
			atlas_hold_motor(50);
		}

		if (drv_awake && !drv_awake_last) {
			t_drv_awake = now;
			m_drv_cfg_ok = false;
		}
		if (!drv_awake && drv_awake_last) {
			m_drv_cfg_ok = false;
			if (!estop_ok) {
				m_estop_openings++;
			}
		}
		if (!drv_awake && !mcpwm_foc_is_dccal_done()) {
			m_dccal_suspect = true;		// the boot calibration saw a sleeping DRV
		}
		drv_awake_last = drv_awake;

		if (drv_awake && mcpwm_foc_is_dccal_done() &&
				ST2MS(chVTTimeElapsedSinceX(t_drv_awake)) >= DRV_WAKE_MS) {
			if (!m_drv_cfg_ok) {
				atlas_hold_motor(DRV_HOLD_AFTER_RESTORE_MS);
				if (atlas_drv_restore()) {
					m_drv_cfg_ok = true;
					atlas_hold_motor(DRV_HOLD_AFTER_RESTORE_MS);
				}
				t_drv_check = now;
			} else if (ST2MS(chVTTimeElapsedSinceX(t_drv_check)) >= DRV_CHECK_MS) {
				t_drv_check = now;
				if (!atlas_drv_gain_ok()) {
					m_drv_cfg_ok = false;	// reset behind our back: restore on the next pass
					m_dccal_suspect = true;
					atlas_hold_motor(DRV_HOLD_AFTER_RESTORE_MS);
				}
			}
		}

		if (!m_drv_cfg_ok && mcpwm_foc_is_dccal_done()) {
			atlas_hold_motor(50);
		}

		// Redo the current offset calibration once the DRV is configured and the motor is still.
		if (m_dccal_suspect && m_drv_cfg_ok && drv_awake && m_pwr_state == PWR_ON &&
				fabsf(mc_interface_get_rpm()) < 200.0) {
			atlas_hold_motor(5000);
			int res = mcpwm_foc_dc_cal(false);
			if (res >= 0 && IS_ESTOP_OK() && atlas_drv_gain_ok()) {
				m_dccal_suspect = false;
			}
			atlas_hold_motor(DRV_HOLD_AFTER_RESTORE_MS);
			t_drv_check = chVTGetSystemTimeX();
		}

		// ---- Jetson (brain board)
		bool halted = palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN);
		bool brain_on = (HW_BRAIN_EN_GPIO->ODR & (1 << HW_BRAIN_EN_PIN));

		if (!halted) {
			jetson_on_ms += SUP_PERIOD_MS;
			jetson_halted_ms = 0;
			if (jetson_on_ms >= JETSON_ON_CONFIRM_MS) {
				m_jetson_seen_on = true;
			}
		} else {
			jetson_halted_ms += SUP_PERIOD_MS;
			jetson_on_ms = 0;
		}

		// Antmicro's SW1 decides whether the module starts by itself when the brain board gets
		// power. If it is still off after a while, press its power button (PWR_SOFT) once, and
		// once more later. Only ever while it is off: the same line is its power key.
		if (pressing) {
			if (ST2MS(chVTTimeElapsedSinceX(t_press_start)) >= JETSON_PRESS_MS) {
				palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
				pressing = false;
			}
		} else if (brain_on && !m_jetson_seen_on && halted && m_jetson_presses < 2 &&
				ST2MS(chVTTimeElapsedSinceX(t_boot)) >= JETSON_PRESS_AFTER_MS &&
				(m_jetson_presses == 0 ||
						ST2MS(chVTTimeElapsedSinceX(t_last_press)) >= JETSON_PRESS_RETRY_MS)) {
			palClearPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
			pressing = true;
			t_press_start = now;
			t_last_press = now;
			m_jetson_presses++;
		}

		// The Jetson shut itself down (sudo poweroff): turn the car off too.
		if (m_jetson_seen_on && jetson_halted_ms >= JETSON_HALT_CONFIRM_MS) {
			m_jetson_seen_on = false;
			if (m_auto_off && !m_poweroff_active) {
				commands_printf("ATLAS: the Jetson halted, turning the car off");
				atlas_power_off(false);
			}
		}

		if (m_poweroff_request && !m_poweroff_active) {
			m_poweroff_request = false;
			atlas_power_off(true);
		}

		chThdSleepMilliseconds(SUP_PERIOD_MS);
	}
}

void hw_init_gpio(void) {
	chMtxObjectInit(&m_poweroff_mutex);

	// GPIO clock enable
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOB, ENABLE);
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC, ENABLE);
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOD, ENABLE);

	// LEDs
	palSetPadMode(GPIOB, 0,
			PAL_MODE_OUTPUT_PUSHPULL |
			PAL_STM32_OSPEED_HIGHEST);
	palSetPadMode(GPIOB, 1,
			PAL_MODE_OUTPUT_PUSHPULL |
			PAL_STM32_OSPEED_HIGHEST);

	// ENABLE_GATE
	palSetPadMode(GPIOB, 5,
			PAL_MODE_OUTPUT_PUSHPULL |
			PAL_STM32_OSPEED_HIGHEST);

	// Disable DCCAL
	palSetPadMode(GPIOD, 2,
			PAL_MODE_OUTPUT_PUSHPULL |
			PAL_STM32_OSPEED_HIGHEST);
	palClearPad(GPIOD, 2);

	ENABLE_GATE();

	// GPIOA Configuration: Channel 1 to 3 as alternate function push-pull
	palSetPadMode(GPIOA, 8, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);
	palSetPadMode(GPIOA, 9, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);
	palSetPadMode(GPIOA, 10, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);

	palSetPadMode(GPIOB, 13, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);
	palSetPadMode(GPIOB, 14, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);
	palSetPadMode(GPIOB, 15, PAL_MODE_ALTERNATE(GPIO_AF_TIM1) |
			PAL_STM32_OSPEED_HIGHEST |
			PAL_STM32_PUDR_FLOATING);

	// Hall sensors
	palSetPadMode(HW_HALL_ENC_GPIO1, HW_HALL_ENC_PIN1, PAL_MODE_INPUT_PULLUP);
	palSetPadMode(HW_HALL_ENC_GPIO2, HW_HALL_ENC_PIN2, PAL_MODE_INPUT_PULLUP);
	palSetPadMode(HW_HALL_ENC_GPIO3, HW_HALL_ENC_PIN3, PAL_MODE_INPUT_PULLUP);

	// Phase filters
	palSetPadMode(PHASE_FILTER_GPIO, PHASE_FILTER_PIN,
			PAL_MODE_OUTPUT_PUSHPULL |
			PAL_STM32_OSPEED_HIGHEST);
	PHASE_FILTER_OFF();

	// Fault pin
	palSetPadMode(GPIOB, 7, PAL_MODE_INPUT_PULLUP);

	// ATLAS: power path and brain board outputs (levels were set in HW_EARLY_INIT), inputs
	palSetPadMode(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_PRECHG_GPIO, HW_PRECHG_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN, PAL_MODE_INPUT);
	palSetPadMode(HW_ESTOP_GPIO, HW_ESTOP_PIN, PAL_MODE_INPUT);
	palSetPadMode(HW_BTN_GPIO, HW_BTN_PIN, PAL_MODE_INPUT);

	// ADC Pins (ATLAS: PA6 is the MAIN_ON output here, not an ADC pin)
	palSetPadMode(GPIOA, 0, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOA, 1, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOA, 2, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOA, 3, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOA, 5, PAL_MODE_INPUT_ANALOG);

	palSetPadMode(GPIOC, 0, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOC, 1, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOC, 2, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOC, 3, PAL_MODE_INPUT_ANALOG);
	palSetPadMode(GPIOC, 4, PAL_MODE_INPUT_ANALOG);

	drv8323s_init();

	terminal_register_command_callback(
		"atlas_status",
		"ATLAS: main switch, E-stop, DRV8323 gain, Jetson and bus current.",
		0,
		terminal_status);

	terminal_register_command_callback(
		"atlas_precharge",
		"ATLAS: precharge the motor bus and close the main switch again (after a fault).",
		0,
		terminal_precharge);

	terminal_register_command_callback(
		"atlas_main_off",
		"ATLAS: open the main switch (motor bus and servo supply off).",
		0,
		terminal_main_off);

	terminal_register_command_callback(
		"atlas_brain",
		"ATLAS: brain board power: on, off, or press (Jetson power button, 0.5 s).",
		"[on|off|press]",
		terminal_brain);

	terminal_register_command_callback(
		"atlas_autooff",
		"ATLAS: 1 = turn the car off when the Jetson halts (default), 0 = leave it on.",
		"[0|1]",
		terminal_autooff);

	terminal_register_command_callback(
		"atlas_poweroff",
		"ATLAS: shut the Jetson down, then turn the car off (same as the power button).",
		0,
		terminal_poweroff);

	terminal_register_command_callback(
		"test_button",
		"Try sampling the shutdown button",
		0,
		terminal_button_test);

	chThdCreateStatic(sup_thread_wa, sizeof(sup_thread_wa), NORMALPRIO + 1, sup_thread, NULL);
}

void hw_setup_adc_channels(void) {
	// ADC1 regular channels
	ADC_RegularChannelConfig(ADC1, ADC_Channel_0, 1, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC1, ADC_Channel_10, 2, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC1, ADC_Channel_5, 3, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC1, ADC_Channel_14, 4, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC1, ADC_Channel_Vrefint, 5, ADC_SampleTime_15Cycles);

	// ADC2 regular channels
	ADC_RegularChannelConfig(ADC2, ADC_Channel_1, 1, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC2, ADC_Channel_11, 2, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC2, ADC_Channel_5, 3, ADC_SampleTime_15Cycles);	// ATLAS: IN5, PA6 is an output
	ADC_RegularChannelConfig(ADC2, ADC_Channel_15, 4, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC2, ADC_Channel_0, 5, ADC_SampleTime_15Cycles);

	// ADC3 regular channels
	ADC_RegularChannelConfig(ADC3, ADC_Channel_2, 1, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC3, ADC_Channel_12, 2, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC3, ADC_Channel_3, 3, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC3, ADC_Channel_13, 4, ADC_SampleTime_15Cycles);
	ADC_RegularChannelConfig(ADC3, ADC_Channel_1, 5, ADC_SampleTime_15Cycles);

	// Injected channels
	ADC_InjectedChannelConfig(ADC1, ADC_Channel_10, 1, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC2, ADC_Channel_11, 1, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC3, ADC_Channel_12, 1, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC1, ADC_Channel_10, 2, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC2, ADC_Channel_11, 2, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC3, ADC_Channel_12, 2, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC1, ADC_Channel_10, 3, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC2, ADC_Channel_11, 3, ADC_SampleTime_15Cycles);
	ADC_InjectedChannelConfig(ADC3, ADC_Channel_12, 3, ADC_SampleTime_15Cycles);
}

void hw_start_i2c(void) {
	i2cAcquireBus(&HW_I2C_DEV);

	if (!i2c_running) {
		palSetPadMode(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN,
				PAL_MODE_ALTERNATE(HW_I2C_GPIO_AF) |
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);
		palSetPadMode(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN,
				PAL_MODE_ALTERNATE(HW_I2C_GPIO_AF) |
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);

		i2cStart(&HW_I2C_DEV, &i2cfg);
		i2c_running = true;
	}

	i2cReleaseBus(&HW_I2C_DEV);
}

void hw_stop_i2c(void) {
	i2cAcquireBus(&HW_I2C_DEV);

	if (i2c_running) {
		palSetPadMode(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN, PAL_MODE_INPUT);
		palSetPadMode(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN, PAL_MODE_INPUT);

		i2cStop(&HW_I2C_DEV);
		i2c_running = false;

	}

	i2cReleaseBus(&HW_I2C_DEV);
}

/**
 * Try to restore the i2c bus
 */
void hw_try_restore_i2c(void) {
	if (i2c_running) {
		i2cAcquireBus(&HW_I2C_DEV);

		palSetPadMode(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN,
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);

		palSetPadMode(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN,
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);

		palSetPad(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN);
		palSetPad(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN);

		chThdSleep(1);

		for(int i = 0;i < 16;i++) {
			palClearPad(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN);
			chThdSleep(1);
			palSetPad(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN);
			chThdSleep(1);
		}

		// Generate start then stop condition
		palClearPad(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN);
		chThdSleep(1);
		palClearPad(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN);
		chThdSleep(1);
		palSetPad(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN);
		chThdSleep(1);
		palSetPad(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN);

		palSetPadMode(HW_I2C_SCL_PORT, HW_I2C_SCL_PIN,
				PAL_MODE_ALTERNATE(HW_I2C_GPIO_AF) |
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);

		palSetPadMode(HW_I2C_SDA_PORT, HW_I2C_SDA_PIN,
				PAL_MODE_ALTERNATE(HW_I2C_GPIO_AF) |
				PAL_STM32_OTYPE_OPENDRAIN |
				PAL_STM32_OSPEED_MID1 |
				PAL_STM32_PUDR_PULLUP);

		HW_I2C_DEV.state = I2C_STOP;
		i2cStart(&HW_I2C_DEV, &i2cfg);

		i2cReleaseBus(&HW_I2C_DEV);
	}
}

// ATLAS: the button is buffered (74LVC1G34) onto PC5, low while pressed. VESC's shutdown thread
// wants true while it is NOT pressed.
bool hw_sample_shutdown_button(void) {
	return palReadPad(HW_BTN_GPIO, HW_BTN_PIN) != 0;
}

static void terminal_status(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	commands_printf("Main switch:  %s (bus %.2f V, last precharge ended at %.2f V)",
			pwr_state_names[m_pwr_state], (double)GET_INPUT_VOLTAGE(), (double)m_precharge_v_end);
	commands_printf("Bus current:  %.1f A (TPS48111 IMON)", (double)hw_atlas_get_bus_current());
	commands_printf("E-stop loop:  %s (%d openings since boot)",
			IS_ESTOP_OK() ? "closed" : "OPEN", m_estop_openings);
	commands_printf("DRV8323:      gate %s, gain %s, %d restores, %d failed, offsets %s",
			IS_GATE_ENABLED() ? "enabled" : "disabled",
			m_drv_cfg_ok ? "40 V/V (checked)" : "NOT CONFIRMED (motor held)",
			m_drv_restores, m_drv_restore_failures,
			m_dccal_suspect ? "to be measured again" : "ok");
	commands_printf("Brain board:  POWER_EN %s, Jetson %s, %d power-button presses, auto-off %s",
			((HW_BRAIN_EN_GPIO->ODR & (1 << HW_BRAIN_EN_PIN))) ? "on" : "off",
			palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN) ? "off (OS_HALTED high)" : "running",
			m_jetson_presses, m_auto_off ? "on" : "off");
	commands_printf("Button:       %s", palReadPad(HW_BTN_GPIO, HW_BTN_PIN) ? "released" : "pressed");
	commands_printf(" ");
}

static void terminal_precharge(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	if (m_pwr_state == PWR_ON) {
		commands_printf("The main switch is already on.");
		return;
	}
	if (m_pwr_state == PWR_PRECHARGE || m_pwr_state == PWR_SHUTTING_DOWN) {
		commands_printf("Busy.");
		return;
	}
	if (ST2MS(chVTTimeElapsedSinceX(m_last_precharge_time)) < PRECHARGE_RETRY_GAP_MS) {
		commands_printf("Wait %d s between tries: the precharge resistors take one pulse at a time.",
				PRECHARGE_RETRY_GAP_MS / 1000);
		return;
	}
	m_precharge_request = true;
	commands_printf("Precharging...");
}

static void terminal_main_off(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	atlas_hold_motor(1000);
	DISABLE_GATE();
	palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
	palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	m_pwr_state = PWR_MAIN_OFF;
	chThdSleepMilliseconds(50);
	ENABLE_GATE();
	commands_printf("Main switch open. atlas_precharge closes it again.");
}

static void terminal_brain(int argc, const char **argv) {
	if (argc != 2) {
		commands_printf("Usage: atlas_brain [on|off|press]");
		return;
	}

	if (strcmp(argv[1], "on") == 0) {
		palSetPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
		commands_printf("Brain board power on.");
	} else if (strcmp(argv[1], "off") == 0) {
		palClearPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
		m_jetson_seen_on = false;
		commands_printf("Brain board power off (without a shutdown: only for a Jetson that is halted or hung).");
	} else if (strcmp(argv[1], "press") == 0) {
		palClearPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
		chThdSleepMilliseconds(JETSON_PRESS_MS);
		palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
		commands_printf("Pressed the Jetson power button (turns it on if off, asks it to shut down if on).");
	} else {
		commands_printf("Usage: atlas_brain [on|off|press]");
	}
}

static void terminal_autooff(int argc, const char **argv) {
	if (argc == 2) {
		m_auto_off = strcmp(argv[1], "0") != 0;
	}
	commands_printf("Auto-off when the Jetson halts: %s (resets to on at the next boot)",
			m_auto_off ? "on" : "off");
}

static void terminal_poweroff(int argc, const char **argv) {
	(void)argc;
	(void)argv;
	m_poweroff_request = true;
	commands_printf("Shutting the Jetson down, then turning the car off.");
}

static void terminal_button_test(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	for (int i = 0;i < 40;i++) {
		commands_printf("BT: %d (1 = released)", HW_SAMPLE_SHUTDOWN());
		chThdSleepMilliseconds(100);
	}
}
