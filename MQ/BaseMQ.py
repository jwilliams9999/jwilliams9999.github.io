#include "BaseMQ.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]

from machine import Pin, ADC
from micropython import const
import utime
from math import exp, log

""" Measuring attempts in cycle """
MQ_SAMPLE_TIMES = const(5)
""" Delay after each measurement, in ms """
MQ_SAMPLE_INTERVAL = const(5000)

""" Heating period, in ms """
MQ_HEATING_PERIOD = const(60000)

""" Cooling period, in ms """
MQ_COOLING_PERIOD = const(90000)

class BaseMQ(object):
    """ Initialization. Pass pinHeader = -1 if heater connected to main power supply """
    """ On troyka modules there is 10K resistor, on other boards could be other values """
    """ Optionally board could run on 3.3 Volds, base voltage is 5.0 Volts """
    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 5.0):
        self._heater = False
        self._cooler = False
        self._ro = -1
        self._useSeparateHeater = False
        self._baseVoltage = baseVoltage
        self._lastMesurement = utime.ticks_ms()
        self._rsCache = None
        self.dataIsReliable = False
        self.pinData = ADC(pinData)
        self._boardResistance = boardResistance
        if pinHeater != -1:
            self.useSeparateHeater = True
            self.pinHeater = Pin(pinHeater, Pin.OUTPUT)
            pass

    """ Abstract method, should be implemented in specific sensor driver """
    def getRoInCleanAir(self):
        raise NotImplementedError("Please Implement this method")

    """ For first time sensor calibration do not pass RO"""
    """ Sensor calibration with known resistance """
    def calibrate(self, ro=-1):
        if ro == -1:
            ro = 0
            print("Calibrating:")
            for i in range(0,MQ_SAMPLE_TIMES + 1):        
                print("Step {0}".format(i))
                ro += self.__calculateResistance__(self.pinData.read())
                utime.sleep_ms(MQ_SAMPLE_INTERVAL)
                pass            
            ro = ro/(self.getRoInCleanAir() * MQ_SAMPLE_TIMES )
            pass
        self._ro = ro
        self._stateCalibrate = True    
        pass

    """ Enable heater """
    def heaterPwrHigh(self):
        #digitalWrite(_pinHeater, HIGH)
        #_pinHeater(1)
        if self._useSeparateHeater:
            self._pinHeater.on()
            pass
        self._heater = True
        self._prMillis = utime.ticks_ms()


    """ Move heater to energy saving mode """
    def heaterPwrLow(self):
        #analogWrite(_pinHeater, 75)
        self._heater = True
        self._cooler = True
        self._prMillis = utime.ticks_ms()


    """ Turn off heater """
    def heaterPwrOff(self):
        if self._useSeparateHeater:
            self._pinHeater.off()
            pass
        #digitalWrite(_pinHeater, LOW)
        _pinHeater(0)
        self._heater = False


    """ Measure sensor resistance value. Could be reused for bypassing true calibration """
    def __calculateResistance__(self, rawAdc):
        vrl = rawAdc*(self._baseVoltage / 1023)
        rsAir = (self._baseVoltage - vrl)/vrl*self._boardResistance
        return rsAir


    """ Data reading """
    """ If data is taken frequently, data reading could be unreliable. Check dataIsReliable flag """
    def __readRs__(self):
        if ( utime.ticks_diff(utime.ticks_ms(),self._lastMesurement) > MQ_SAMPLE_INTERVAL * MQ_SAMPLE_TIMES) :        
            rs = 0
            for i in range(0, MQ_SAMPLE_TIMES + 1): 
                rs += self.__calculateResistance__(self.pinData.read())
                utime.sleep_ms(MQ_SAMPLE_INTERVAL)

            rs = rs/MQ_SAMPLE_TIMES
            self._rsCache = rs
            self.dataIsReliable = True
            self._lastMesurement = utime.ticks_ms()
        else:
            rs = self.__calculateResistance__(self.pinData.read())
            self.dataIsReliable = False
            # rs = self._rsCache
        return rs


    def readScaled(self, a, b):        
        return exp((log(self.readRatio())-b)/a)


    def readRatio(self):
        return self.__readRs__()/self._ro


    def heatingCompleted(self):
        if (self._heater) and (not self._cooler) and (utime.ticks_diff(utime.ticks_ms(),self._prMillis) > MQ_HEATING_PERIOD):
            return True
        else:
            return False


    def coolanceCompleted(self):
        if (self._heater) and (self._cooler) and (utime.ticks_diff(utime.ticks_ms(), self._prMillis) > MQ_COOLING_PERIOD):
            return True
        else:
            return False


    def cycleHeat(self):
        self._heater = False
        self._cooler = False
        self.heaterPwrHigh()
    #ifdef MQDEBUG
        print("Heated sensor")
    #endif #MQDEBUG
        pass


    def atHeatCycleEnd(self):
        if self.heatingCompleted():
            self.heaterPwrLow()
    #ifdef MQDEBUG
            print("Cool sensor")
    #endif #MQDEBUG
            return False

        elif self.coolanceCompleted():
            self.heaterPwrOff()
            return True

        else:
            return False

