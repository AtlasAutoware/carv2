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
 * The motor side keeps the HD60 pin map (gate PWM, shunt amps, phase sense, halls, DRV8323 SPI,
 * USART3, CAN, servo on PB6), so VESC Tool treats it like an HD60. What differs, marked ATLAS:
 *   - 0.2 mOhm shunts, CSA gain 40, pack limits (4S3P Molicel P28A)
 *   - IMU is an LSM6DS3TR-C on bit-banged I2C, SCL PA15 and SDA PC11 (PB2 stays BOOT1)
 *   - power: no hold pin. A 74LVC1G74 latch keeps the board on; the button sets it and the MCU
 *     clears it with KILL (PB12 high). The button is read on PC5 (BTN_SENSE, low = pressed).
 *   - main switch: TPS48111, MCU-sequenced. PA7 PRECHG_ON (INP_G), then PA6 MAIN_ON (INP),
 *     IMON on PA5 (46 V/V over 0.2 mOhm)
 *   - brain board: PA4 POWER_EN, PC14 power-button request to the Jetson (low = shut down),
 *     PC15 OS_HALTED from the Jetson (high = halted or off)
 *   - PC10 reads the E-stop loop (high = closed). The loop also gates DRV EN in hardware.
 *   - no permanent UART, no NRF SWD and no SPI encoder on PA5-PA7: those pins drive the power
 *     path here. An SPI encoder uses the hall connector (hw.h default).
 */
#ifndef HW_ATLAS_DRV1_H_
#define HW_ATLAS_DRV1_H_

#include "drv8323s.h"

#define HW_NAME					"ATLAS_DRV1"	// ATLAS

// HW properties
#define HW_HAS_DRV8323S
#define HW_HAS_3_SHUNTS
#define HW_HAS_PHASE_FILTERS

// Macros
#define ENABLE_GATE()			palSetPad(GPIOB, 5)
#define DISABLE_GATE()			palClearPad(GPIOB, 5)

#define IS_DRV_FAULT()			(!palReadPad(GPIOB, 7))

#define LED_GREEN_ON()			palSetPad(GPIOB, 0)
#define LED_GREEN_OFF()			palClearPad(GPIOB, 0)
#define LED_RED_ON()			palSetPad(GPIOB, 1)
#define LED_RED_OFF()			palClearPad(GPIOB, 1)

// Shutdown pin
// ATLAS: the latch holds power; KILL (PB12 high) clears it. Button sense on PC5, low = pressed.
#define HW_KILL_GPIO			GPIOB
#define HW_KILL_PIN				12
#define HW_BTN_GPIO				GPIOC
#define HW_BTN_PIN				5
#define HW_SHUTDOWN_HOLD_ON()	palClearPad(HW_KILL_GPIO, HW_KILL_PIN)
#define HW_SHUTDOWN_HOLD_OFF()	hw_power_off()
#define HW_SAMPLE_SHUTDOWN()	hw_sample_shutdown_button()

// ATLAS: main switch and brain board power
#define HW_PRECHG_GPIO			GPIOA
#define HW_PRECHG_PIN			7
#define HW_MAIN_ON_GPIO			GPIOA
#define HW_MAIN_ON_PIN			6
#define HW_BRAIN_EN_GPIO		GPIOA
#define HW_BRAIN_EN_PIN			4
#define HW_JETSON_REQ_GPIO		GPIOC		// low = ask the Jetson to shut down
#define HW_JETSON_REQ_PIN		14
#define HW_JETSON_HALTED_GPIO	GPIOC		// high = Jetson halted (or brain board off)
#define HW_JETSON_HALTED_PIN	15
#define HW_ESTOP_GPIO			GPIOC		// high = E-stop loop closed
#define HW_ESTOP_PIN			10
#define IS_ESTOP_OK()			palReadPad(HW_ESTOP_GPIO, HW_ESTOP_PIN)

// Keep KILL low and the power path off from the first instruction
#define HW_EARLY_INIT()			palSetPadMode(HW_KILL_GPIO, HW_KILL_PIN, PAL_MODE_OUTPUT_PUSHPULL); \
								HW_SHUTDOWN_HOLD_ON(); \
								palSetPadMode(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN, PAL_MODE_OUTPUT_PUSHPULL); \
								palClearPad(HW_MAIN_ON_GPIO, HW_MAIN_ON_PIN); \
								palSetPadMode(HW_PRECHG_GPIO, HW_PRECHG_PIN, PAL_MODE_OUTPUT_PUSHPULL); \
								palClearPad(HW_PRECHG_GPIO, HW_PRECHG_PIN);

#define PHASE_FILTER_GPIO		GPIOC
#define PHASE_FILTER_PIN		13
#define PHASE_FILTER_ON()		palSetPad(PHASE_FILTER_GPIO, PHASE_FILTER_PIN)
#define PHASE_FILTER_OFF()		palClearPad(PHASE_FILTER_GPIO, PHASE_FILTER_PIN)

/*
 * ADC Vector
 *
 * 0:	IN0		SENS1
 * 1:	IN1		SENS2
 * 2:	IN2		SENS3
 * 3:	IN10	CURR1
 * 4:	IN11	CURR2
 * 5:	IN12	CURR3
 * 6:	IN5		ADC_EXT1 (ATLAS: main switch IMON)
 * 7:	IN5		ADC_EXT2 (ATLAS: IMON again; PA6 is the MAIN_ON output)
 * 8:	IN3		TEMP_PCB
 * 9:	IN14	TEMP_MOTOR
 * 10:	IN15	Shutdown
 * 11:	IN13	AN_IN
 * 12:	Vrefint
 * 13:	IN0		SENS1
 * 14:	IN1		SENS2
 */

#define HW_ADC_CHANNELS			15
#define HW_ADC_INJ_CHANNELS		3
#define HW_ADC_NBR_CONV			5

// ADC Indexes
#define ADC_IND_SENS1			0
#define ADC_IND_SENS2			1
#define ADC_IND_SENS3			2
#define ADC_IND_CURR1			3
#define ADC_IND_CURR2			4
#define ADC_IND_CURR3			5
#define ADC_IND_VIN_SENS		11
#define ADC_IND_EXT				6
#define ADC_IND_EXT2			7
#define ADC_IND_TEMP_MOS		8
#define ADC_IND_TEMP_MOTOR		9
#define ADC_IND_VREFINT			12
#define ADC_IND_SHUTDOWN		10

// ADC macros and settings

// Component parameters (can be overridden)
#ifndef V_REG
#define V_REG					3.3
#endif
#ifndef VIN_R1
#define VIN_R1					39000.0
#endif
#ifndef VIN_R2
#define VIN_R2					2200.0
#endif
#ifndef CURRENT_AMP_GAIN
#define CURRENT_AMP_GAIN		40.0	// ATLAS: DRV8323 GAIN pin set to 40 V/V
#endif
#ifndef CURRENT_SHUNT_RES
#define CURRENT_SHUNT_RES		0.0002	// ATLAS: 0.2 mOhm, 3920 metal strip
#endif

// Input voltage
#define GET_INPUT_VOLTAGE()		((V_REG / 4095.0) * (float)ADC_Value[ADC_IND_VIN_SENS] * ((VIN_R1 + VIN_R2) / VIN_R2))

// NTC Termistors
#define NTC_RES(adc_val)		((4095.0 * 10000.0) / adc_val - 10000.0)
#define NTC_TEMP(adc_ind)		(1.0 / ((logf(NTC_RES(ADC_Value[adc_ind]) / 10000.0) / 3380.0) + (1.0 / 298.15)) - 273.15)

#define NTC_RES_MOTOR(adc_val)	(10000.0 / ((4095.0 / (float)adc_val) - 1.0)) // Motor temp sensor on low side
#define NTC_TEMP_MOTOR(beta)	(1.0 / ((logf(NTC_RES_MOTOR(ADC_Value[ADC_IND_TEMP_MOTOR]) / 10000.0) / beta) + (1.0 / 298.15)) - 273.15)

// Voltage on ADC channel
#define ADC_VOLTS(ch)			((float)ADC_Value[ch] / 4096.0 * V_REG)

// Double samples in beginning and end for positive current measurement.
// Useful when the shunt sense traces have noise that causes offset.
#ifndef CURR1_DOUBLE_SAMPLE
#define CURR1_DOUBLE_SAMPLE		0
#endif
#ifndef CURR2_DOUBLE_SAMPLE
#define CURR2_DOUBLE_SAMPLE		0
#endif
#ifndef CURR3_DOUBLE_SAMPLE
#define CURR3_DOUBLE_SAMPLE		0
#endif

// COMM-port ADC GPIOs (ATLAS: both on PA5 / IMON so nothing ever turns PA6 into an input)
#define HW_ADC_EXT_GPIO			GPIOA
#define HW_ADC_EXT_PIN			5
#define HW_ADC_EXT2_GPIO		GPIOA
#define HW_ADC_EXT2_PIN			5

// UART Peripheral
#define HW_UART_DEV				SD3
#define HW_UART_GPIO_AF			GPIO_AF_USART3
#define HW_UART_TX_PORT			GPIOB
#define HW_UART_TX_PIN			10
#define HW_UART_RX_PORT			GPIOB
#define HW_UART_RX_PIN			11

// ATLAS: no permanent UART (PC10 is the E-stop sense, PC11 the IMU SDA)

// ICU Peripheral for servo decoding
#define HW_USE_SERVO_TIM4
#define HW_ICU_TIMER			TIM4
#define HW_ICU_TIM_CLK_EN()		RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM4, ENABLE)
#define HW_ICU_DEV				ICUD4
#define HW_ICU_CHANNEL			ICU_CHANNEL_1
#define HW_ICU_GPIO_AF			GPIO_AF_TIM4
#define HW_ICU_GPIO				GPIOB
#define HW_ICU_PIN				6

// I2C Peripheral
#define HW_I2C_DEV				I2CD2
#define HW_I2C_GPIO_AF			GPIO_AF_I2C2
#define HW_I2C_SCL_PORT			GPIOB
#define HW_I2C_SCL_PIN			10
#define HW_I2C_SDA_PORT			GPIOB
#define HW_I2C_SDA_PIN			11

// Hall/encoder pins
#define HW_HALL_ENC_GPIO1		GPIOC
#define HW_HALL_ENC_PIN1		6
#define HW_HALL_ENC_GPIO2		GPIOC
#define HW_HALL_ENC_PIN2		7
#define HW_HALL_ENC_GPIO3		GPIOC
#define HW_HALL_ENC_PIN3		8
#define HW_ENC_TIM				TIM3
#define HW_ENC_TIM_AF			GPIO_AF_TIM3
#define HW_ENC_TIM_CLK_EN()		RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3, ENABLE)
#define HW_ENC_EXTI_PORTSRC		EXTI_PortSourceGPIOC
#define HW_ENC_EXTI_PINSRC		EXTI_PinSource8
#define HW_ENC_EXTI_LINE		EXTI_Line8
#define HW_ENC_TIM_ISR_CH		TIM3_IRQn
#define HW_ENC_TIM_ISR_VEC		TIM3_IRQHandler

// ATLAS: no SPI port on PA5-PA7 (power path control). hw.h puts an SPI encoder on the hall pins.
// There is no NRF radio either, but VESC always builds its software-SPI NRF driver, and hw.h
// would aim it at the missing SPI port. Aim it at the hall connector instead (the encoder pins
// plus the motor-temperature pin as MOSI). It only runs if the NRF app is turned on, which this
// board has no use for. It must never land on PA5-PA7.
#define NRF_PORT_CSN			HW_HALL_ENC_GPIO3
#define NRF_PIN_CSN				HW_HALL_ENC_PIN3
#define NRF_PORT_SCK			HW_HALL_ENC_GPIO1
#define NRF_PIN_SCK				HW_HALL_ENC_PIN1
#define NRF_PORT_MOSI			GPIOC
#define NRF_PIN_MOSI			4
#define NRF_PORT_MISO			HW_HALL_ENC_GPIO2
#define NRF_PIN_MISO			HW_HALL_ENC_PIN2

// SPI for DRV8323S
#define DRV8323S_MOSI_GPIO		GPIOC
#define DRV8323S_MOSI_PIN		12
#define DRV8323S_MISO_GPIO		GPIOB
#define DRV8323S_MISO_PIN		3
#define DRV8323S_SCK_GPIO		GPIOB
#define DRV8323S_SCK_PIN		4
#define DRV8323S_CS_GPIO		GPIOC
#define DRV8323S_CS_PIN			9

// LSM6DS3TR-C (ATLAS): WHO_AM_I 0x6A, accepted by imu/lsm6ds3.c
#define IMU_DEV				IMU_DEV_LSM6DS3
#define IMU_COM				IMU_COM_I2C_BB
#define IMU_I2C_SDA_GPIO		GPIOC		// ATLAS: PC11 (HD60 uses PB2)
#define IMU_I2C_SDA_PIN			11
#define IMU_I2C_SCL_GPIO		GPIOA
#define IMU_I2C_SCL_PIN			15
#define IMU_FLIP

// ATLAS: no NRF SWD (PB12 is KILL, PA4 the brain board enable)

// Measurement macros
#define ADC_V_L1				ADC_Value[ADC_IND_SENS1]
#define ADC_V_L2				ADC_Value[ADC_IND_SENS2]
#define ADC_V_L3				ADC_Value[ADC_IND_SENS3]
#define ADC_V_ZERO				(ADC_Value[ADC_IND_VIN_SENS] / 2)

// Macros
#define READ_HALL1()			palReadPad(HW_HALL_ENC_GPIO1, HW_HALL_ENC_PIN1)
#define READ_HALL2()			palReadPad(HW_HALL_ENC_GPIO2, HW_HALL_ENC_PIN2)
#define READ_HALL3()			palReadPad(HW_HALL_ENC_GPIO3, HW_HALL_ENC_PIN3)

// Default setting overrides
#ifndef MCCONF_L_CURRENT_MAX
#define MCCONF_L_CURRENT_MAX				70.0	// ATLAS	// Current limit in Amperes (Upper)
#endif
#ifndef MCCONF_L_CURRENT_MIN
#define MCCONF_L_CURRENT_MIN				-40.0	// ATLAS: regen into the pack stays under the BMS OCC trip	// Current limit in Amperes (Lower)
#endif
#ifndef MCCONF_L_IN_CURRENT_MAX
#define MCCONF_L_IN_CURRENT_MAX				90.0	// ATLAS: under the BMS OCD1 trip (~140 A)	// Input current limit in Amperes (Upper)
#endif
#ifndef MCCONF_L_IN_CURRENT_MIN
#define MCCONF_L_IN_CURRENT_MIN				-12.0	// ATLAS: charge-direction limit, about 4 A per cell for 4S3P P28A	// Input current limit in Amperes (Lower)
#endif
#ifndef MCCONF_L_MAX_ABS_CURRENT
#define MCCONF_L_MAX_ABS_CURRENT			180.0	// ATLAS	// The maximum absolute current above which a fault is generated
#endif
#ifndef MCCONF_M_DRV8301_OC_ADJ
#define MCCONF_M_DRV8301_OC_ADJ				10 // DRV8301 over current protection threshold
#endif

#ifndef MCCONF_DEFAULT_MOTOR_TYPE
#define MCCONF_DEFAULT_MOTOR_TYPE		MOTOR_TYPE_FOC
#endif
#ifndef MCCONF_FOC_F_ZV
#define MCCONF_FOC_F_ZV					30000.0
#endif

#ifndef MCCONF_M_DRV8301_OC_MODE
#define MCCONF_M_DRV8301_OC_MODE		DRV8301_OC_LATCH_SHUTDOWN // DRV8301 over current protection mode
#endif

// ATLAS: pack defaults (4S3P Molicel P28A, 3.0 V/cell cutoff start, 2.8 V end)
#ifndef MCCONF_L_BATTERY_CUT_START
#define MCCONF_L_BATTERY_CUT_START		12.0
#endif
#ifndef MCCONF_L_BATTERY_CUT_END
#define MCCONF_L_BATTERY_CUT_END		11.2
#endif
#ifndef MCCONF_SI_BATTERY_CELLS
#define MCCONF_SI_BATTERY_CELLS			4
#endif
#ifndef MCCONF_SI_BATTERY_AH
#define MCCONF_SI_BATTERY_AH			8.4
#endif

// Setting limits
#define HW_LIM_CURRENT			-120.0, 120.0	// ATLAS
#define HW_LIM_CURRENT_IN		-60.0, 110.0	// ATLAS
#define HW_LIM_CURRENT_ABS		0.0, 200.0	// ATLAS
#define HW_LIM_VIN				6.0, 26.0	// ATLAS: 40 V FETs, 35 V bulk caps; 4S nominal, 6S max
#define HW_LIM_ERPM				-200e3, 200e3
#define HW_LIM_DUTY_MIN			0.0, 0.1
#define HW_LIM_DUTY_MAX			0.0, 0.99
#define HW_LIM_TEMP_FET			-40.0, 110.0

// Functions
bool hw_sample_shutdown_button(void);
void hw_power_off(void);	// ATLAS: Jetson shutdown handshake, then KILL

#endif /* HW_ATLAS_DRV1_H_ */
