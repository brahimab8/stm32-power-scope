# USB-CDC Setup (STM32L432)

> **Note:** This guide focuses on STM32CubeIDE USB-CDC bring-up on STM32L432 (wiring, clocks, and CDC integration).
> For the current Power Scope protocol and architecture, see `docs/protocol.md` and `docs/architecture.md`.

**Goal:** bring up USB CDC on STM32L432KC and verify end-to-end byte transport (with a simple echo path).

**Contents**

- [USB-CDC Setup (STM32L432)](#usb-cdc-setup-stm32l432)
  - [Hardware Setup and Wiring](#hardware-setup-and-wiring)
  - [STM32CubeIDE Setup](#stm32cubeide-setup)
    - [Sanity checklist](#sanity-checklist)
  - [Verify Echo](#verify-echo)
  - [Troubleshooting](#troubleshooting)
  - [References](#references)

---

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

## Verify Echo

Extend CDC to forward RX to an application callback

**`USB_DEVICE/App/usbd_cdc_if.h`**

```c
typedef void (*cdc_rx_cb_t)(const uint8_t* data, uint32_t len);
void USBD_CDC_SetRxCallback(cdc_rx_cb_t cb);
```

**`USB_DEVICE/App/usbd_cdc_if.c`**

```c
static cdc_rx_cb_t s_rx_cb = 0;

void USBD_CDC_SetRxCallback(cdc_rx_cb_t cb) { s_rx_cb = cb; }

static int8_t CDC_Receive_FS(uint8_t* Buf, uint32_t *Len)
{
    if (s_rx_cb) s_rx_cb(Buf, *Len);      // forward to app
    USBD_CDC_SetRxBuffer(&hUsbDeviceFS, &Buf[0]);
    USBD_CDC_ReceivePacket(&hUsbDeviceFS);
    return USBD_OK;
}
```

**Thin application layer (`app/comm_usb_cdc.[ch]`)**
In this repo, USB-CDC is wrapped by a small transport module (`comm_usb_cdc.*`) that:

- registers a CDC RX callback (`USBD_CDC_SetRxCallback`) and forwards received bytes to an app handler (`comm_usb_cdc_set_rx_handler()`),
- provides link gating via `comm_usb_cdc_link_ready()` (USB configured + DTR asserted + TX ready),
- provides a staged write API `comm_usb_cdc_try_write()` that copies into an internal buffer (safe for stack/volatile caller buffers).

To verify end-to-end CDC I/O, register an RX handler that echoes bytes back:

```c
static void on_rx(const uint8_t* data, uint32_t len)
{
    /* best-effort echo; ignore partial/busy conditions for bring-up */
    (void)comm_usb_cdc_try_write(data, (uint16_t)len);
}

int main(void)
{
    /* ... HAL/Cube init ... */
    comm_usb_cdc_init();
    comm_usb_cdc_set_rx_handler(on_rx);

    while (1) {
        /* main loop */
    }
}
```

## Troubleshooting

* **No COM port appears:** check D+/D− pins, HSI48 + CRS, and `HAL_PWREx_EnableVddUSB()`.
* **Random disconnects:** try a different USB cable/port; disable USB selective suspend / power saving on the host.

---

## References

- [STM32Cube™ USB Device Library (UM1734)](https://www.st.com/resource/en/user_manual/um1734-stm32cube-usb-device-library-stmicroelectronics.pdf)  
- [Beyond Logic — USB in a Nutshell: Endpoint Types (bulk, FS 64-byte packets)](https://www.beyondlogic.org/usbnutshell/usb4.shtml)  
