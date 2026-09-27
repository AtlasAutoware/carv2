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
 * Atlas Autoware ATLAS-DRV-1 (car v2 drive board). DRAFT, not yet built or tested on hardware.
 * Derived from hwconf/trampa/hd/hw_hd60.{h,c} (Copyright 2019 Benjamin Vedder, GPL-3.0-or-later).
 * See hw_atlas_drv1.h for what differs from the HD60. Changes are marked ATLAS.
 */
#include "hw.h"

#include <math.h>

#include "ch.h"
#include "hal.h"
#include "stm32f4xx_conf.h"
#include "utils_math.h"
#include "drv8323s.h"
#include "terminal.h"
#include "commands.h"
#include "mc_interface.h"

// Variables
static volatile bool i2c_running = false;
static mutex_t shutdown_mutex;
static float bt_diff = 0.0;

// I2C configuration
static const I2CConfig i2cfg = {
		OPMODE_I2C,
		100000,
		STD_DUTY_CYCLE
};

// Private functions
static void terminal_shutdown_now(int argc, const char **argv);
static void terminal_button_test(int argc, const char **argv);

// ATLAS: main switch bring-up. Precharge the 1.4 mF bus through 2 x 22 Ohm (tau 16 ms), wait until
// VM has settled, then close the main FETs. A bus that does not charge stays off. The precharge
// resistors are rated for one charging pulse (about 0.1 J each), not for a short on VM (13 W each):
// if VM is still under 4 V after 10 ms the precharge gate goes off at once (sim/precharge.py).
static THD_WORKING_AREA(power_seq_thread_wa, 512);
static volatile bool main_switch_on = false;

static THD_FUNCTION(power_seq_thread, arg) {
	(void)arg;
	chRegSetThreadName("Power seq");

	chThdSleepMilliseconds(300);	// ADC running and filtered

	palSetPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	chThdSleepMilliseconds(10);
	float last = GET_INPUT_VOLTAGE();
	bool charged = false;
	if (last > 4.0) {					// a healthy bus is near 8 V by now
		for (int i = 0;i < 15;i++) {	// then up to 300 ms to settle
			chThdSleepMilliseconds(20);
			float v = GET_INPUT_VOLTAGE();
			if (v > 9.0 && fabsf(v - last) < 0.1) {
				charged = true;
				break;
			}
			last = v;
		}
	}

	if (charged) {
		palSetPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
		chThdSleepMilliseconds(50);
		main_switch_on = true;
	}
	palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);

	// the brain board runs while the car is on
	palSetPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);

	if (!charged) {
		for (;;) {			// blink red: bus did not precharge
			LED_RED_ON();
			chThdSleepMilliseconds(200);
			LED_RED_OFF();
			chThdSleepMilliseconds(800);
		}
	}
}

void hw_init_gpio(void) {
	chMtxObjectInit(&shutdown_mutex);

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

	// ATLAS: power path, brain board handshake, E-stop and button sense
	palSetPadMode(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_PRECHG_GPIO, HW_PRECHG_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPadMode(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palClearPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
	palSetPadMode(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN, PAL_MODE_OUTPUT_PUSHPULL);
	palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
	palSetPadMode(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN, PAL_MODE_INPUT);
	palSetPadMode(HW_ESTOP_GPIO, HW_ESTOP_PIN, PAL_MODE_INPUT);
	palSetPadMode(HW_BTN_GPIO, HW_BTN_PIN, PAL_MODE_INPUT);

	// ADC Pins (ATLAS: PA6 is not an ADC pin here, it drives MAIN_ON)
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
		"shutdown",
		"Shutdown VESC now.",
		0,
		terminal_shutdown_now);

	terminal_register_command_callback(
		"test_button",
		"Try sampling the shutdown button",
		0,
		terminal_button_test);

	chThdCreateStatic(power_seq_thread_wa, sizeof(power_seq_thread_wa), NORMALPRIO, power_seq_thread, NULL);	// ATLAS
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

// ATLAS: the button is buffered (74LVC1G34) onto PC5, low while pressed
bool hw_sample_shutdown_button(void) {
	chMtxLock(&shutdown_mutex);
	bool pressed = !palReadPad(HW_BTN_GPIO, HW_BTN_PIN);
	bt_diff = pressed ? 1.0 : 0.0;
	chMtxUnlock(&shutdown_mutex);
	return pressed;
}

// ATLAS: ask the Jetson to shut down (1 s low on its power-button line), wait up to 30 s for
// OS_HALTED, then drop the brain board, open the main switch and clear the power latch.
void hw_power_off(void) {
	DISABLE_GATE();

	if (!palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN)) {
		palClearPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
		chThdSleepMilliseconds(1000);
		palSetPad(HW_JETSON_REQ_GPIO, HW_JETSON_REQ_PIN);
		for (int i = 0;i < 300 && !palReadPad(HW_JETSON_HALTED_GPIO, HW_JETSON_HALTED_PIN);i++) {
			chThdSleepMilliseconds(100);
		}
	}

	palClearPad(HW_BRAIN_EN_GPIO, HW_BRAIN_EN_PIN);
	palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN);
	palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);
	chThdSleepMilliseconds(10);
	palSetPad(HW_KILL_GPIO, HW_KILL_PIN);		// latch cleared: 3V3 and the MCU go down
}

static void terminal_shutdown_now(int argc, const char **argv) {
	(void)argc;
	(void)argv;
	DISABLE_GATE();
	HW_SHUTDOWN_HOLD_OFF();
}

static void terminal_button_test(int argc, const char **argv) {
	(void)argc;
	(void)argv;

	for (int i = 0;i < 40;i++) {
		commands_printf("BT: %d %.2f", HW_SAMPLE_SHUTDOWN(), (double)bt_diff);
		chThdSleepMilliseconds(100);
	}
}
