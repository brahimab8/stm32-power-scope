# USB-CDC Setup: Bring-up & Smoke Test

**Goal:** prove USB CDC works end-to-end by creating our own thin communication layer on top of the Cube-generated USB device, with a simple echo test.

## Hardware Setup and Wiring

* **MCU board:** STM32-L432KC (USB FS capable)
* **Programmer:** ST-LINK (SWD)
* **USB cable:** 4-wire for power + comm
* **USB D+/D− wiring:** **D+ (green) → PA12**, **D− (white) → PA11**, and **GND** common
  *(VBUS/red to board 5 V only if you intend to be bus-powered.)*
* **Nucleo-32 note:** If you need standalone 5 V power without the ST-LINK USB connected, **check UM1956** for your board revision; you may need to remove a solder bridge (often **SB9**) related to **NRST** to avoid hold/reset when ST-LINK is absent.
* **Single power source caution:** Do **not** tie the PC’s 5 V to an external 5 V at the same time (avoid back-powering).

## STM32CubeIDE Setup

1. **New project** — Create a project for **STM32L432KC**; Debug = **Serial Wire**.

2. **Connectivity** — Enable the peripherals you need.

   * **USB (Device FS):** **Enable**
     *VBUS sensing:* set to **Disabled / B-device without VBUS** (option wording varies by Cube version).

3. **Middleware → USB\_DEVICE** — Select the device class.

   * **Class for FS IP:** **Communication Device Class (Virtual COM Port)**.

4. **System Core → RCC** — Configure clock recovery for USB.

   * **CRS SYNC Source:** **USB** (lets HSI48 auto-trim to 48 MHz).

5. **Clock Configuration** — Ensure correct USB clocking.

   * Use **Resolve Clock Issues**, or manually set **USB clock = HSI48 (48 MHz)**.

6. **Generate Code** — Verify init order and a couple of USB settings.

   * Ensure `MX_USB_DEVICE_Init()` is called **after** clocks are configured.
   * In `USB_DEVICE/Target/usbd_conf.h`, set:

     * `#define USBD_LPM_ENABLED 0U`
       *(LPM isn’t needed for CDC; avoiding it reduces suspend/resume quirks.)*
     * `#define USBD_SELF_POWERED 0U`  ← **Most projects** (bus-powered from the PC).
       Set to `1U` **only if** the device is **self-powered** (its own supply) and USB 5 V isn’t the source.
   * In `USB_DEVICE/Target/usbd_conf.c`, check that **VDDUSB** is enabled:

     * Either `HAL_PWREx_EnableVddUSB();` appears in `USBD_LL_Init()`, **or** you enabled “VddUSB” via Cube if supported for your MCU family.
       *(This powers the internal USB analog cell.)*

### Sanity checklist

* D+ on **PA12**, D− on **PA11** (Nucleo FS boards don’t need extra series resistors; the embedded PHY handles this).
* CRS enabled and **HSI48** selected for USB.
* `USBD_LPM_ENABLED = 0U` unless you truly support LPM.
* `USBD_SELF_POWERED` matches your power topology (likely `0U`).
* Only one power source at a time.

---

## Smoke Test

### 1. Extend the USB device layer

* In `USB_DEVICE/App/usbd_cdc_if.h` — define the callback type:

  ```c
  typedef void (*cdc_rx_cb_t)(const uint8_t* data, uint32_t len);
  ```

  Declare a setter:

  ```c
  void USBD_CDC_SetRxCallback(cdc_rx_cb_t cb);
  ```

* In `USB_DEVICE/App/usbd_cdc_if.c` — store the callback:

  ```c
  static cdc_rx_cb_t s_rx_cb = 0;
  ```

  Provide the setter:

  ```c
  void USBD_CDC_SetRxCallback(cdc_rx_cb_t cb) { s_rx_cb = cb; }
  ```

  Forward from `CDC_Receive_FS`:

  ```c
  static int8_t CDC_Receive_FS(uint8_t* Buf, uint32_t *Len)
  {
      if (s_rx_cb) s_rx_cb(Buf, *Len);      // forward to app
      USBD_CDC_SetRxBuffer(&hUsbDeviceFS, &Buf[0]);
      USBD_CDC_ReceivePacket(&hUsbDeviceFS);
      return (USBD_OK);
  }
  ```

---

### 2. Create a thin application layer

We add a small module `comm_usb_cdc` to wrap transmit and forward RX to an app handler.

* `app/comm_usb_cdc.h` — public API:

  ```c
  #pragma once
  #include <stdint.h>

  typedef void (*comm_rx_handler_t)(const uint8_t* data, uint32_t len);

  void comm_usb_cdc_init(void);
  int  comm_usb_cdc_write(const void* buf, uint16_t len);
  void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb);
  void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len);
  ```

* `app/comm_usb_cdc.c` — implementation:

  ```c
  #include "app/comm_usb_cdc.h"
  #include "usbd_cdc_if.h"

  static comm_rx_handler_t s_rx = 0;

  void comm_usb_cdc_init(void) {
      s_rx = 0;
      USBD_CDC_SetRxCallback(comm_usb_cdc_on_rx_bytes);
  }

  int comm_usb_cdc_write(const void* buf, uint16_t len) {
      return (CDC_Transmit_FS((uint8_t*)buf, len) == USBD_OK) ? (int)len : -1;
  }

  void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb) { s_rx = cb; }

  void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len) {
      if (s_rx) s_rx(data, len);
  }
  ```

---

### 3. Hook into `main.c` for the smoke test

We hook up a trivial echo handler to confirm that communication works.

* Include the header:

  ```c
  #include "app/comm_usb_cdc.h"
  ```

* Define a simple echo callback:

  ```c
  static void usb_rx_echo(const uint8_t* data, uint32_t len)
  {
      (void)comm_usb_cdc_write(data, (uint16_t)len);
  }
  ```

* Initialize (Cube order is fine; handler can be set before or after USB init):

  ```c
  MX_USB_DEVICE_Init();
  comm_usb_cdc_init();
  comm_usb_cdc_set_rx_handler(usb_rx_echo);
  ```

---

## Expected outcome

* PC enumerates a **Virtual COM Port** for the device.
* Opening the port at any baud (CDC ignores it) and typing sends bytes to the MCU.
* The device **echoes** back the exact bytes.

## Troubleshooting

* **No COM port appears:** check D+/D− pins, HSI48 + CRS, `HAL_PWREx_EnableVddUSB()`.
* **Echo doesn’t return:** confirm `USBD_LPM_ENABLED = 0U`, and that your terminal actually **opens** the port (no OUT data is sent until then).
* **Random disconnects:** try a different USB cable/port; disable USB selective suspend / power saving on the host.
