#!/usr/bin/env python
# -*- coding: utf8 -*-

from periphery import GPIO, SPI
import time

class MFRC522:
    # Coral Dev Board 物理引腳 Pin 22 (Reset) 對應核心編號 73
    NRSTPD_PIN = 73

    MAX_LEN = 16

    # MFRC522 指令常數
    PCD_IDLE       = 0x00
    PCD_AUTHENT    = 0x0E
    PCD_RECEIVE    = 0x08
    PCD_TRANSMIT   = 0x04
    PCD_TRANSCEIVE = 0x0C
    PCD_RESETPHASE = 0x0F
    PCD_CALCCRC    = 0x03

    PICC_REQIDL    = 0x26
    PICC_ANTICOLL  = 0x93
    PICC_SElECTTAG = 0x93
    PICC_AUTHENT1A = 0x60
    PICC_READ      = 0x30
    PICC_WRITE     = 0xA0

    MI_OK       = 0
    MI_NOTAGERR = 1
    MI_ERR      = 2

    # 暫存器位址
    CommandReg     = 0x01
    CommIEnReg     = 0x02
    CommIrqReg     = 0x04
    DivIrqReg      = 0x05
    ErrorReg       = 0x06
    Status2Reg     = 0x08
    FIFODataReg    = 0x09
    FIFOLevelReg   = 0x0A
    ControlReg     = 0x0C
    BitFramingReg  = 0x0D
    ModeReg        = 0x11
    TxControlReg   = 0x14
    TxAutoReg      = 0x15
    TModeReg       = 0x2A
    TPrescalerReg  = 0x2B
    TReloadRegH    = 0x2C
    TReloadRegL    = 0x2D

    def __init__(self, dev='/dev/spidev0.0', spd=1000000):
        self.spi = SPI(dev, 0, spd)
        try:
            self.gpio_rst = GPIO(self.NRSTPD_PIN, "out")
        except Exception as e:
            print("GPIO Error: " + str(e))
            raise
        self.gpio_rst.write(True)
        self.Init()

    def __del__(self):
        if hasattr(self, 'spi'): self.spi.close()
        if hasattr(self, 'gpio_rst'):
            self.gpio_rst.write(False)
            self.gpio_rst.close()

    def Write_MFRC522(self, addr, val):
        self.spi.transfer([(addr << 1) & 0x7E, val])

    def Read_MFRC522(self, addr):
        val = self.spi.transfer([((addr << 1) & 0x7E) | 0x80, 0])
        return val[1]

    def SetBitMask(self, reg, mask):
        self.Write_MFRC522(reg, self.Read_MFRC522(reg) | mask)
    def ClearBitMask(self, reg, mask):
        self.Write_MFRC522(reg, self.Read_MFRC522(reg) & (~mask))

    def AntennaOn(self):
        if not (self.Read_MFRC522(self.TxControlReg) & 0x03):
            self.SetBitMask(self.TxControlReg, 0x03)

    def Init(self):
        self.gpio_rst.write(True)
        self.Write_MFRC522(self.CommandReg, self.PCD_RESETPHASE)
        self.Write_MFRC522(self.TModeReg, 0x8D)
        self.Write_MFRC522(self.TPrescalerReg, 0x3E)
        self.Write_MFRC522(self.TReloadRegL, 30)
        self.Write_MFRC522(self.TReloadRegH, 0)
        self.Write_MFRC522(self.TxAutoReg, 0x40)
        self.Write_MFRC522(self.ModeReg, 0x3D)
        self.AntennaOn()

    def ToCard(self, command, sendData):
        backData = []
        backLen = 0
        status = self.MI_ERR
        irqEn = 0x00
        waitIRq = 0x00

        if command == self.PCD_AUTHENT:
            irqEn = 0x12
            waitIRq = 0x10
        if command == self.PCD_TRANSCEIVE:
            irqEn = 0x77
            waitIRq = 0x30

        self.Write_MFRC522(self.CommIEnReg, irqEn | 0x80)
        self.ClearBitMask(self.CommIrqReg, 0x80)
        self.SetBitMask(self.FIFOLevelReg, 0x80)
        self.Write_MFRC522(self.CommandReg, self.PCD_IDLE)

        for d in sendData:
            self.Write_MFRC522(self.FIFODataReg, d)
        self.Write_MFRC522(self.CommandReg, command)
        if command == self.PCD_TRANSCEIVE:
            self.SetBitMask(self.BitFramingReg, 0x80)

        i = 2000
        while True:
            n = self.Read_MFRC522(self.CommIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x01) and not (n & waitIRq)):
                break

        self.ClearBitMask(self.BitFramingReg, 0x80)

        if i != 0:
            if (self.Read_MFRC522(self.ErrorReg) & 0x1B) == 0x00:
                status = self.MI_OK
                if n & irqEn & 0x01: status = self.MI_NOTAGERR
                if command == self.PCD_TRANSCEIVE:
                    n = self.Read_MFRC522(self.FIFOLevelReg)
                    lastBits = self.Read_MFRC522(self.ControlReg) & 0x07
                    backLen = (n - 1) * 8 + lastBits if lastBits != 0 else n * 8
                    if n == 0: n = 1
                    if n > self.MAX_LEN: n = self.MAX_LEN
                    for _ in range(n):
                        backData.append(self.Read_MFRC522(self.FIFODataReg))

        return (status, backData, backLen)

    def Request(self, reqMode):
        self.Write_MFRC522(self.BitFramingReg, 0x07)
        (status, backData, backBits) = self.ToCard(self.PCD_TRANSCEIVE, [reqMode])
        if (status != self.MI_OK) or (backBits != 0x10): status = self.MI_ERR
        return (status, backBits)

    def Anticoll(self):
        self.Write_MFRC522(self.BitFramingReg, 0x00)
        (status, backData, backBits) = self.ToCard(self.PCD_TRANSCEIVE, [self.PICC_ANTICOLL, 0x20])
        if status == self.MI_OK:
            if len(backData) == 5:
                check = 0
                for i in range(4): check ^= backData[i]
                if check != backData[4]: status = self.MI_ERR
            else: status = self.MI_ERR
        return (status, backData)

    def SelectTag(self, serNum):
        # 簡化版 SelectTag，主要用於門禁驗證
        return self.MI_OK