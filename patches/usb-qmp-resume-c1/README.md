# Preserve PIPE clock ownership on QMP USB initialization timeout

The Fedora Cerro suspend journal shows the USB PCS timing out on resume,
then DWC3 returning `-ETIMEDOUT`. An xHCI retry timed out and the clock
framework reported that `gcc_usb3_prim_phy_pipe_clk` had already been disabled
and unprepared. The backtrace points to `qmp_combo_usb_power_on()`.

In the Cerro tree, the common combo block owns the PIPE clock. The USB
PCS helper does not acquire it. The correction leaves common clock cleanup
to `qmp_combo_com_exit()` and still propagates the USB PCS error.
Successful initialization and suspend policy are unmodified.

Tree commit `6bf0ee34154d96bab5cb14780b007b06b40574e2` builds with
`ARCH=arm64 LLVM=1 LOCALVERSION=-fedora-zram` using the
`drivers/phy/qualcomm/phy-qcom-qmp-combo.o` target.
This candidate is compiled only. The underlying PHY timeout and real
USB recovery after deep suspend still need physical acceptance.
