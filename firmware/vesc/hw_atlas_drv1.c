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
#include "utils_sys.h"
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
#define PRECHARGE_RETRY_GAP_MS		15000	// between precharges (resistor pulse rating)
#define BUS_LOST_V					6.0		// the motor bus below this while on: the main switch tripped
#define BUS_LOST_MS					20
#define TRIP_AUTO_RETRIES			3		// automatic precharges after trips, then only atlas_precharge
#define DRV_WAKE_MS					2		// DRV8323 wake-up before SPI works (datasheet ~1 ms)
#define DRV_HOLD_AFTER_RESTORE_MS	500		// keep the motor released after a restore
#define DCCAL_GOOD_CFG_MS			1500	// the boot offsets count if the gain was right this long before
#define JETSON_PRESS_AFTER_MS		5000	// press the power button if the module is still off
#define JETSON_PRESS_MS				500
#define JETSON_PRESS_RETRY_MS		20000
#define JETSON_ON_CONFIRM_MS		1000	// OS_HALTED low this long = module running
#define JETSON_HALT_CONFIRM_MS		3000	// OS_HALTED high this long after running = module halted
#define JETSON_SHUTDOWN_PRESS_MS	1000	// power-key event length for a shutdown request
#define JETSON_SHUTDOWN_REPRESS_MS	10000	// press again this often while it has not halted
#define JETSON_SHUTDOWN_WAIT_MS		60000	// then give up waiting and switch off
#define BUTTON_SAMPLES				3		// consecutive low samples (10 ms apart) for a press

typedef enum {
	PWR_WAIT_ADC = 0,
	PWR_PRECHARGE,
	PWR_ON,
	PWR_FAULT_SHORT,		// the bus did not rise: something on VM is shorted
	PWR_FAULT_TIMEOUT,		// the bus did not settle in time
	PWR_MAIN_OFF,			// opened on purpose (terminal)
	PWR_TRIPPED,			// the bus collapsed while on (TPS48111 over-current trip, most likely)
	PWR_SHUTTING_DOWN,
} atlas_pwr_state;

static const char *pwr_state_names[] = {
		"waiting for ADC", "precharging", "on", "FAULT: bus shorted (did not rise)",
		"FAULT: bus did not settle", "main switch off (terminal)",
		"TRIPPED: bus lost while on, main switch opened", "shutting down"
};

static THD_WORKING_AREA(sup_thread_wa, 2048);
static volatile atlas_pwr_state m_pwr_state = PWR_WAIT_ADC;
static volatile bool m_precharge_request = true;		// run once at boot
static volatile bool m_precharge_done_once = false;
static volatile systime_t m_last_precharge_time = 0;
static volatile float m_precharge_v_end = 0.0;
static volatile int m_trips = 0;

static volatile bool m_drv_cfg_ok = false;			// CSA gain read back as 40 V/V since the last wake
static volatile bool m_dccal_suspect = false;		// current offsets measured with the DRV not ready
static volatile int m_drv_restores = 0;
static volatile int m_drv_restore_failures = 0;
static volatile int m_estop_openings = 0;

static volatile bool m_jetson_seen_on = false;		// running now (for halt detection)
static volatile bool m_jetson_ever_on = false;		// ran since the brain board got power
static volatile int m_jetson_presses = 0;
static volatile systime_t m_brain_on_time = 0;
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

// Milliseconds since t. ST2MS() overflows 32 bits after about 7 minutes at 10 kHz.
static float age_ms(systime_t t) {
	return UTILS_AGE_S(t) * 1000.0f;
}

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

// One-off: motor released and user commands ignored for the next ms milliseconds. Only valid
// once mc_interface is running (its first DC calibration done). Logs two events, so the
// supervisor loop does not call it every pass.
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
	m_precharge_done_once = true;

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

// DRV8323 settings as drv8323s_init() and mc_interface_init() leave them. The DRV8323 runs from
// the switched bus (VM), so it starts with its defaults (20 V/V) after every precharge, and it
// resets whenever ENABLE stays low for about a millisecond (E-stop).
static bool atlas_drv_restore(void) {
	const volatile mc_configuration *conf = mc_interface_get_configuration();

	if (atlas_drv_gain_ok()) {
		return true;	// awake and still configured
	}

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

// Press the Jetson's power key (SLEEP/WAKE*, through PWR_SOFT on the brain board).
static void jetson_press(int ms) {
	palClearPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
	chThdSleepMilliseconds(ms);
	palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
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
		// A key press during the Jetson's own boot is lost, so press again every 10 s until it
		// halts. Only while it runs: the same line switches a halted module back on.
		jetson_press(JETSON_SHUTDOWN_PRESS_MS);
		int halted_ms = 0;
		int since_press_ms = 0;
		for (int t = 0;t < JETSON_SHUTDOWN_WAIT_MS && halted_ms < 500;t += 50) {
			chThdSleepMilliseconds(50);
			since_press_ms += 50;
			DISABLE_GATE();
			if (palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN)) {
				halted_ms += 50;
			} else {
				halted_ms = 0;
				if (since_press_ms >= JETSON_SHUTDOWN_REPRESS_MS) {
					jetson_press(JETSON_SHUTDOWN_PRESS_MS);
					since_press_ms = 0;
				}
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
	while (ADC_Value[ADC_IND_VREFINT] < 1000 && age_ms(t_start) < 3000.0f) {
		chThdSleepMilliseconds(5);
	}
	chThdSleepMilliseconds(20);

	m_brain_on_time = chVTGetSystemTimeX();
	bool drv_awake_last = false;
	systime_t t_drv_awake = m_brain_on_time;
	systime_t t_cfg_ok = m_brain_on_time;
	bool dccal_done_last = false;
	int hold_ms = 0;
	bool motor_held = false;
	int bus_low_ms = 0;
	systime_t t_trip = m_brain_on_time;
	systime_t t_press_start = 0;
	bool pressing = false;
	systime_t t_last_press = 0;
	int jetson_on_ms = 0;
	int jetson_halted_ms = 0;

	for (;;) {
		systime_t now = chVTGetSystemTimeX();
		bool dccal_done = mcpwm_foc_is_dccal_done();

		// ---- main switch
		if (m_precharge_request) {
			m_precharge_request = false;
			atlas_precharge();
			now = chVTGetSystemTimeX();
		}

		// A TPS48111 trip opens the FETs and its timer re-closes them 15 s later with no
		// precharge. Watch the bus: if it collapses, drop MAIN_ON so the chip stays off, and
		// precharge again after the pulse-rating gap (a few times at most).
		if (m_pwr_state == PWR_ON) {
			if (GET_INPUT_VOLTAGE() < BUS_LOST_V) {
				bus_low_ms += SUP_PERIOD_MS;
				if (bus_low_ms >= BUS_LOST_MS) {
					palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
					palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
					m_pwr_state = PWR_TRIPPED;
					m_trips++;
					t_trip = now;
					commands_printf("ATLAS: motor bus lost while on (trip %d), main switch opened", m_trips);
				}
			} else {
				bus_low_ms = 0;
			}
		} else {
			bus_low_ms = 0;
		}
		if (m_pwr_state == PWR_TRIPPED && m_trips <= TRIP_AUTO_RETRIES &&
				age_ms(t_trip) >= (float)PRECHARGE_RETRY_GAP_MS &&
				age_ms(m_last_precharge_time) >= (float)PRECHARGE_RETRY_GAP_MS) {
			m_precharge_request = true;
		}

		// ---- E-stop and DRV8323 configuration. The DRV8323 is only powered and awake with the
		// bus up, the E-stop loop closed and PB5 high.
		bool estop_ok = IS_ESTOP_OK();
		bool drv_awake = estop_ok && IS_GATE_ENABLED() && m_pwr_state == PWR_ON;

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
		drv_awake_last = drv_awake;

		if (drv_awake && age_ms(t_drv_awake) >= (float)DRV_WAKE_MS) {
			if (!m_drv_cfg_ok) {
				if (atlas_drv_restore()) {
					m_drv_cfg_ok = true;
					t_cfg_ok = now;
					hold_ms = DRV_HOLD_AFTER_RESTORE_MS;
				}
			} else if (!atlas_drv_gain_ok()) {
				m_drv_cfg_ok = false;			// reset behind our back: restore on the next pass
				commands_printf("ATLAS: DRV8323 lost its settings, restoring");
			}
		}

		// VESC measures the current-sensor offsets once at boot, about a second after the bus
		// comes up. They are only right if the DRV8323 had its 40 V/V gain the whole time.
		if (dccal_done && !dccal_done_last) {
			m_dccal_suspect = !(m_drv_cfg_ok && age_ms(t_cfg_ok) >= (float)DCCAL_GOOD_CFG_MS);
		}
		dccal_done_last = dccal_done;

		// Motor released and commands ignored while any of this is not right
		bool need_hold = !estop_ok || !m_drv_cfg_ok || m_pwr_state != PWR_ON || hold_ms > 0;
		if (hold_ms > 0) {
			hold_ms -= SUP_PERIOD_MS;
		}
		if (dccal_done && need_hold) {
			mc_interface_ignore_input_both(50);
			if (!motor_held) {
				mc_interface_release_motor_override_both();
				motor_held = true;
			}
		} else {
			motor_held = false;
		}

		// Measure the offsets again when the boot measurement was not trustworthy: DRV ready,
		// motor still, commands locked out while VESC's calibration runs (about 1.4 s).
		if (m_dccal_suspect && dccal_done && m_drv_cfg_ok && drv_awake && !IS_DRV_FAULT() &&
				fabsf(mc_interface_get_rpm()) < 200.0) {
			mc_interface_lock();
			mc_interface_release_motor_override_both();
			int res = mcpwm_foc_dc_cal(false);	// unlocks mc_interface when it completes
			if (res < 0) {
				mc_interface_unlock();
			}
			if (res >= 0 && IS_ESTOP_OK() && atlas_drv_gain_ok()) {
				m_dccal_suspect = false;
			}
			hold_ms = DRV_HOLD_AFTER_RESTORE_MS;
			now = chVTGetSystemTimeX();
		}

		// ---- Jetson (brain board)
		bool halted = palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN);
		bool brain_on = (HW_BRAIN_EN_GPIO->ODR & (1 << HW_BRAIN_EN_PIN));

		if (!halted) {
			jetson_on_ms += SUP_PERIOD_MS;
			jetson_halted_ms = 0;
			if (jetson_on_ms >= JETSON_ON_CONFIRM_MS) {
				m_jetson_seen_on = true;
				m_jetson_ever_on = true;
			}
		} else {
			jetson_halted_ms += SUP_PERIOD_MS;
			jetson_on_ms = 0;
		}

		// Antmicro's SW1 decides whether the module starts by itself when the brain board gets
		// power. If it has not started a while after the brain board got power, press its power
		// button once, and once more later. Never after it has run: a Jetson that was shut down
		// on purpose stays down.
		if (pressing) {
			if (age_ms(t_press_start) >= (float)JETSON_PRESS_MS) {
				palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
				pressing = false;
			}
		} else if (brain_on && !m_jetson_ever_on && halted && m_jetson_presses < 2 &&
				age_ms(m_brain_on_time) >= (float)JETSON_PRESS_AFTER_MS &&
				(m_jetson_presses == 0 || age_ms(t_last_press) >= (float)JETSON_PRESS_RETRY_MS)) {
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
// samples every 10 ms and wants true while it is NOT pressed; a press counts after
// BUTTON_SAMPLES low samples in a row, so a spike on the remote button lead does not.
bool hw_sample_shutdown_button(void) {
	static int low_samples = 0;
	if (palReadPad(HW_BTN_GPIO, HW_BTN_PIN) == 0) {
		if (low_samples < BUTTON_SAMPLES) {
			low_samples++;
		}
	} else {
		low_samples = 0;
	}
	return low_samples < BUTTON_SAMPLES;
}

static void terminal_status(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	commands_printf("Main switch:  %s (bus %.2f V, last precharge ended at %.2f V, %d trips)",
			pwr_state_names[m_pwr_state], (double)GET_INPUT_VOLTAGE(), (double)m_precharge_v_end, m_trips);
	commands_printf("Bus current:  %.1f A (TPS48111 IMON)", (double)hw_atlas_get_bus_current());
	commands_printf("E-stop loop:  %s (%d openings since boot)",
			IS_ESTOP_OK() ? "closed" : "OPEN", m_estop_openings);
	commands_printf("DRV8323:      gate %s, gain %s, %d restores, %d failed, offsets %s",
			IS_GATE_ENABLED() ? "enabled" : "disabled",
			m_drv_cfg_ok ? "40 V/V (checked)" : "NOT CONFIRMED (motor held)",
			m_drv_restores, m_drv_restore_failures,
			m_dccal_suspect ? "to be measured again (motor still, E-stop closed)" : "ok");
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
	if (m_precharge_done_once && age_ms(m_last_precharge_time) < (float)PRECHARGE_RETRY_GAP_MS) {
		commands_printf("Wait %d s between tries: the precharge resistors take one pulse at a time.",
				PRECHARGE_RETRY_GAP_MS / 1000);
		return;
	}
	m_trips = 0;
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
		if (!(HW_BRAIN_EN_GPIO->ODR & (1 << HW_BRAIN_EN_PIN))) {
			m_jetson_ever_on = false;		// a fresh start: the power-button help applies again
			m_jetson_presses = 0;
			m_brain_on_time = chVTGetSystemTimeX();
		}
		palSetPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
		commands_printf("Brain board power on.");
	} else if (strcmp(argv[1], "off") == 0) {
		palClearPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
		m_jetson_seen_on = false;
		commands_printf("Brain board power off (without a shutdown: only for a Jetson that is halted or hung).");
	} else if (strcmp(argv[1], "press") == 0) {
		jetson_press(JETSON_PRESS_MS);
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
