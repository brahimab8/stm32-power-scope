# USB-CDC Setup & Streaming

**Goal:** bring up USB CDC on STM32L432KC, verify echo over a thin app layer, then enable a robust streaming path (ring + pump + DTR).

**Contents**

- [USB-CDC Setup \& Streaming](#usb-cdc-setup--streaming)
  - [Hardware Setup and Wiring](#hardware-setup-and-wiring)
  - [STM32CubeIDE Setup](#stm32cubeide-setup)
    - [Sanity checklist](#sanity-checklist)
  - [Verify Echo](#verify-echo)
  - [Streaming mode (ring + pump + DTR)](#streaming-mode-ring--pump--dtr)
    - [Firmware integration in the Cube device layer](#firmware-integration-in-the-cube-device-layer)
    - [Module layout (firmware)](#module-layout-firmware)
    - [Host Shell (Python)](#host-shell-python)
    - [Expected behavior](#expected-behavior)
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

Extend CDC to forward RX to your app.

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
Wrap transmit (`CDC_Transmit_FS`) and expose `comm_usb_cdc_set_rx_handler()`.
In `main.c`, register a trivial echo handler to prove end-to-end comms.

---

## Streaming mode (ring + pump + DTR)

Turn the echo path into a **robust streamer** that keeps producing even when the host pauses:

* **Ring buffer** (overwrite-oldest) between producer and USB
* **TX pump**: submits ≤512 B only when **CONFIGURED + DTR asserted + previous TX complete**
* **Framing**: 16-byte header (MAGIC `0x5AA5`), fields include `seq` and `ts_ms`
* **Commands**: 1-byte **START (0x01)** / **STOP (0x02)**

### Firmware integration in the Cube device layer

**`USB_DEVICE/App/usbd_cdc_if.c`** — add (inside a `USER CODE` block):

```c
#include <stdbool.h>
extern void comm_usb_cdc_on_tx_complete(void);
extern void comm_usb_cdc_on_dtr_change(bool asserted);
```

Hook the callbacks:

```c
// TX complete → allow next chunk
static int8_t CDC_TransmitCplt_FS(uint8_t *Buf, uint32_t *Len, uint8_t epnum)
{
  (void)Buf; (void)Len; (void)epnum;
  /* USER CODE BEGIN 13 */
  comm_usb_cdc_on_tx_complete();
  /* USER CODE END 13 */
  return USBD_OK;
}
```

```c
// Host DTR → start/stop streaming
static int8_t CDC_Control_FS(uint8_t cmd, uint8_t* pbuf, uint16_t length)
{
  switch (cmd) {
    case CDC_SET_CONTROL_LINE_STATE: {
      extern USBD_HandleTypeDef hUsbDeviceFS;
      bool dtr = (hUsbDeviceFS.request.wValue & 0x0001u) != 0u; // bit0
      comm_usb_cdc_on_dtr_change(dtr);
      break;
    }
    default: break;
  }
  return USBD_OK;
}
```

### Module layout (firmware)

* `app/ring_buffer.h` — SPSC byte ring (power-of-two, overwrite-oldest)
* `app/comm_usb_cdc.[ch]` — link gating + `comm_usb_cdc_pump(rb_t*)` + IRQ hooks
* `app/protocol_defs.h`, `app/protocol.c` — 16-byte header (MAGIC `0x5AA5`, LE), `START/STOP` helpers
* `app/board.h`, `app/board_stm32l432.c` — `board_millis()` shim (no HAL in app code)
* `app/ps_config.h` — ring sizes, stream cadence, RX budget
* `app/ps_app.[ch]` — owns TX/RX rings, frames via `ps_send_frame()`, parses START/STOP, calls pump
* `main.c` — `ps_app_init();` then `ps_app_tick();` in the loop

### Host Shell (Python)

A small CLI opens the CDC port, asserts **DTR**, optionally sends **START/STOP**, and prints frames.

**Setup**

```bash
# from repo root
python -m pip install -r host/requirements.txt
```

**Run**

```bash
# Auto-detect the CDC port
python -m host.cli.shell

# Or specify a port explicitly
#   Windows: python -m host.cli.shell -p COM6
#   Linux:   python -m host.cli.shell -p /dev/ttyACM0
#   macOS:   python -m host.cli.shell -p /dev/tty.usbmodem*

# Optional on open:
#   --start  (send START once)
#   --stop   (send STOP once)
```

### Expected behavior

* One line per frame: `seq`, `ts_ms`, `len`, `gap`.
  *`gap > 1` implies at least gap−1 frames were missed on the host side (e.g., backlog overran and oldest were dropped).*
* Closing the port drops **DTR** → stream pauses; reopening resumes.
* Mid-stream opens auto-**resync** on the 2-byte magic (`A5 5A` on the wire).

---

## Troubleshooting

* **No COM port appears:** check D+/D− pins, HSI48 + CRS, and `HAL_PWREx_EnableVddUSB()`.
* **Echo/stream doesn’t return:** ensure your tool **asserts DTR** (the provided shell does).
* **Random disconnects:** try a different USB cable/port; disable USB selective suspend / power saving on the host.
* **Auto-detect failed:** run with `-p <port>` and verify the device shows up in Device Manager (Windows) or `/dev/ttyACM*` (Linux/macOS).

---

## References

- [STM32Cube™ USB Device Library (UM1734)](https://www.st.com/resource/en/user_manual/um1734-stm32cube-usb-device-library-stmicroelectronics.pdf)  
- [Beyond Logic — USB in a Nutshell: Endpoint Types (bulk, FS 64-byte packets)](https://www.beyondlogic.org/usbnutshell/usb4.shtml)  
