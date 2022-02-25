# -*- coding: utf-8 -*-
"""
Created on Thu Oct  7 12:40:05 2021

@author: José Miguel Algarín Guisado
MRILAB @ I3M
"""

import sys
# marcos_client path for linux
sys.path.append('../marcos_client')
# marcos_client and PhysioMRI_GUI for Windows
sys.path.append('D:\CSIC\REPOSITORIOS\marcos_client')
sys.path.append('D:\CSIC\REPOSITORIOS\PhysioMRI_GUI')
import numpy as np
import experiment as ex
import matplotlib.pyplot as plt
import scipy.signal as sig
import os
from scipy.io import savemat
from datetime import date,  datetime 
import pdb
from configs.hw_config import Gx_factor
from configs.hw_config import Gy_factor
from configs.hw_config import Gz_factor
st = pdb.set_trace



#*********************************************************************************
#*********************************************************************************
#*********************************************************************************


def rare_standalone(
    init_gpa=False,              # Starts the gpa
    nScans = 1,                 # NEX
    larmorFreq = 3.07622e6,      # Larmor frequency
    rfExAmp = 0.3,             # rf excitation pulse amplitude
    rfReAmp = 0.3,             # rf refocusing pulse amplitude
    rfExTime = 35e-6,          # rf excitation pulse time
    rfReTime = 70e-6,            # rf refocusing pulse time
    echoSpacing = 20e-3,        # time between echoes
    inversionTime = 0,       # Inversion recovery time
    repetitionTime = 500e-3,     # TR
    fov = np.array([12e-2, 12e-2, 12e-2]),           # FOV along readout, phase and slice
    dfov = np.array([0e-2, 0e-2, 0e-2]),            # Displacement of fov center
    nPoints = np.array([60, 60, 1]),                 # Number of points along readout, phase and slice
    etl = 10,                    # Echo train length
    acqTime = 2e-3,             # Acquisition time
    axes = np.array([0, 1, 2]),       # 0->x, 1->y and 2->z defined as [rd,ph,sl]
    axesEnable = np.array([1, 0, 0]), # 1-> Enable, 0-> Disable
    sweepMode = 1,               # 0->k2k (T2),  1->02k (T1),  2->k20 (T2), 3->Niquist modulated (T2)
    phaseGradTime = 1000e-6,       # Phase and slice dephasing time
    rdPreemphasis = 1.005,
    drfPhase = 0,                           # phase of the excitation pulse (in degrees)
    dummyPulses = 1,                     # Dummy pulses for T1 stabilization
    shimming = np.array([-70, -90, 10]),       # Shimming along the X,Y and Z axes (a.u. *1e4)
    parAcqLines = 0                        # Number of additional lines, Full sweep if 0
    ):
    
    # rawData fields
    rawData = {}
    inputs = {}
    outputs = {}
    auxiliar = {}
    
    # Miscellaneous
    killingPhaseGradient = 1    # multiply phase gradient by this number
    blkTime = 10             # Deblanking time (us)
    larmorFreq = larmorFreq*1e-6
    gradRiseTime = 400e-6       # Estimated gradient rise time
    gSteps = int(gradRiseTime*1e6/5)    # Gradient ramp steps
    gradDelay = 9            # Gradient amplifier delay
    addRdPoints = 10             # Initial rd points to avoid artifact at the begining of rd
    gammaB = 42.56e6            # Gyromagnetic ratio in Hz/T
    rfReAmp = rfExAmp
    rfReTime = 2*rfExTime
    if axesEnable[0]==0:
        oversamplingFactor = 60
    else:
        oversamplingFactor = 6
    addRdGradTime = 1000     # Additional readout gradient time to avoid turn on/off effects on the Rx channel
    shimming = shimming*1e-4
    auxiliar['gradDelay'] = gradDelay*1e-6
    auxiliar['gradRiseTime'] = gradRiseTime
    auxiliar['oversamplingFactor'] = oversamplingFactor
    auxiliar['addRdGradTime'] = addRdGradTime*1e-6
    
    # Matrix size
    nRD = nPoints[0]+2*addRdPoints
    nPH = nPoints[1]*axesEnable[1]+(1-axesEnable[1])
    nSL = nPoints[2]*axesEnable[2]+(1-axesEnable[2])
    nPoints[1] = nPH
    nPoints[2] = nSL
    
    # Inputs for rawData
    inputs['nScans'] = nScans
    inputs['larmorFreq'] = larmorFreq      # Larmor frequency
    inputs['rfExAmp'] = rfExAmp             # rf excitation pulse amplitude
    inputs['rfReAmp'] = rfReAmp             # rf refocusing pulse amplitude
    inputs['rfExTime'] = rfExTime          # rf excitation pulse time
    inputs['rfReTime'] = rfReTime            # rf refocusing pulse time
    inputs['echoSpacing'] = echoSpacing        # time between echoes
    inputs['inversionTime'] = inversionTime       # Inversion recovery time
    inputs['repetitionTime'] = repetitionTime     # TR
    inputs['fov'] = fov           # FOV along readout, phase and slice
    inputs['dfov'] = dfov            # Displacement of fov center
    inputs['nPoints'] = nPoints                 # Number of points along readout, phase and slice
    inputs['etl'] = etl                    # Echo train length
    inputs['acqTime'] = acqTime             # Acquisition time
    inputs['axes'] = axes       # 0->x, 1->y and 2->z defined as [rd,ph,sl]
    inputs['axesEnable'] = axesEnable # 1-> Enable, 0-> Disable
    inputs['sweepMode'] = sweepMode               # 0->k2k (T2),  1->02k (T1),  2->k20 (T2), 3->Niquist modulated (T2)
    inputs['phaseGradTime'] = phaseGradTime       # Phase and slice dephasing time
    inputs['rdPreemphasis'] = rdPreemphasis
    inputs['drfPhase'] = drfPhase 
    inputs['dummyPulses'] = dummyPulses                    # Dummy pulses for T1 stabilization
    inputs['shimming'] = shimming
    inputs['parAcqLines'] = parAcqLines
    
    # ETL if nPH = 1
    if etl>nPH:
        etl = nPH
    
    # parAcqLines in case parAcqLines = 0
    if parAcqLines==0:
        parAcqLines = int(nSL/2)
    
    # BW
    BW = nPoints[0]/acqTime*1e-6
    BWov = BW*oversamplingFactor
    samplingPeriod = 1/BWov
    
    # Readout dephasing time
    rdDephTime = (acqTime-gradRiseTime)/2
    
    # Phase and slice de- and re-phasing time
    if phaseGradTime==0:
        phaseGradTime = echoSpacing/2-rfExTime/2-rfReTime/2-2*gradRiseTime
    elif phaseGradTime>echoSpacing/2-rfExTime/2-rfReTime/2-2*gradRiseTime:
        phaseGradTime = echoSpacing/2-rfExTime/2-rfReTime/2-2*gradRiseTime
        
    # Max gradient amplitude
    rdGradAmplitude = nPoints[0]/(gammaB*fov[0]*acqTime)*axesEnable[0]
    phGradAmplitude = nPH/(2*gammaB*fov[1]*(phaseGradTime+gradRiseTime))*axesEnable[1]*killingPhaseGradient
    slGradAmplitude = nSL/(2*gammaB*fov[2]*(phaseGradTime+gradRiseTime))*axesEnable[2]

    # Change gradient values to OCRA units
    gFactor = reorganizeGfactor(axes)
    rdGradAmplitude = rdGradAmplitude/gFactor[0]*1000/10
    phGradAmplitude = phGradAmplitude
    slGradAmplitude = slGradAmplitude
    
    # Phase and slice gradient vector
    phGradients = np.linspace(-phGradAmplitude,phGradAmplitude,num=nPH,endpoint=False)
    slGradients = np.linspace(-slGradAmplitude,slGradAmplitude,num=nSL,endpoint=False)
    auxiliar['phGradients'] = phGradients
    auxiliar['slGradients'] = slGradients
    phGradients = phGradients/gFactor[1]*1000/10
    slGradients = slGradients/gFactor[2]*1000/10
    
    # Set phase vector to given sweep mode
    ind = getIndex(phGradients, etl, nPH, sweepMode)
    phGradients = phGradients[::-1]
    phGradients = phGradients[ind]

    # Initialize the experiment
    expt = ex.Experiment(lo_freq=larmorFreq, rx_t=samplingPeriod, init_gpa=init_gpa, gpa_fhdo_offset_time=(1 / 0.2 / 3.1))
    samplingPeriod = expt.get_rx_ts()[0]
    BW = 1/samplingPeriod/oversamplingFactor
    acqTime = nPoints[0]/BW        # us
    auxiliar['bandwidth'] = BW*1e6
    
    # Create an rf pulse function
    def rfPulse(tStart,rfTime,rfAmplitude,rfPhase):
        txTime = np.array([tStart+blkTime,tStart+blkTime+rfTime])
        txAmp = np.array([rfAmplitude*np.exp(1j*rfPhase),0.])
        txGateTime = np.array([tStart,tStart+blkTime+rfTime])
        txGateAmp = np.array([1,0])
        expt.add_flodict({
            'tx0': (txTime, txAmp),
            'tx_gate': (txGateTime, txGateAmp)
            })

    # Readout function
    def rxGate(tStart,gateTime):
        rxGateTime = np.array([tStart,tStart+gateTime])
        rxGateAmp = np.array([1,0])
        expt.add_flodict({
            'rx0_en':(rxGateTime, rxGateAmp), 
            'rx_gate': (rxGateTime, rxGateAmp), 
            })

    # Gradients
    def gradTrap(tStart, gTime, gAmp, gAxis):
        tUp = np.linspace(tStart, tStart+gradRiseTime, num=gSteps, endpoint=False)
        tDown = tUp+gradRiseTime+gTime
        t = np.concatenate((tUp, tDown), axis=0)
        dAmp = gAmp/gSteps
        aUp = np.linspace(dAmp, gAmp, num=gSteps)
        aDown = np.linspace(gAmp-dAmp, 0, num=gSteps)
        a = np.concatenate((aUp, aDown), axis=0)
        if gAxis==0:
            expt.add_flodict({'grad_vx': (t, a+shimming[0])})
        elif gAxis==1:
            expt.add_flodict({'grad_vy': (t, a+shimming[1])})
        elif gAxis==2:
            expt.add_flodict({'grad_vz': (t, a+shimming[2])})
    
    def gradPulse(tStart, gTime, gAmp,  gAxes):
        t = np.array([tStart, tStart+gradRiseTime+gTime])
        for gIndex in range(np.size(gAxes)):
            a = np.array([gAmp[gIndex], 0])
            if gAxes[gIndex]==0:
                expt.add_flodict({'grad_vx': (t, a+shimming[0])})
            elif gAxes[gIndex]==1:
                expt.add_flodict({'grad_vy': (t, a+shimming[1])})
            elif gAxes[gIndex]==2:
                expt.add_flodict({'grad_vz': (t, a+shimming[2])})
    
    def endSequence(tEnd):
        expt.add_flodict({
                'grad_vx': (np.array([tEnd]),np.array([0]) ), 
                'grad_vy': (np.array([tEnd]),np.array([0]) ), 
                'grad_vz': (np.array([tEnd]),np.array([0]) ),
             })
             
    def iniSequence(tEnd, shimming):
        expt.add_flodict({
                'grad_vx': (np.array([tEnd]),np.array([shimming[0]]) ), 
                'grad_vy': (np.array([tEnd]),np.array([shimming[1]]) ), 
                'grad_vz': (np.array([tEnd]),np.array([shimming[2]]) ),
             })

    # Changing time parameters to us
    rfExTime = rfExTime*1e6
    rfReTime = rfReTime*1e6
    echoSpacing = echoSpacing*1e6
    repetitionTime = repetitionTime*1e6
    gradRiseTime = gradRiseTime*1e6
    phaseGradTime = phaseGradTime*1e6
    rdDephTime = rdDephTime*1e6
    inversionTime = inversionTime*1e6
    
    # Create sequence instructions
    phIndex = 0
    slIndex = 0
    scanTime = (nPH*nSL/etl+dummyPulses)*repetitionTime
    # Set shimming
    iniSequence(20, shimming)
    for repeIndex in range(int(nPH*nSL/etl)+dummyPulses):
        # Initialize time
        t0 = 20+repetitionTime*repeIndex
        
        # Inversion pulse
        if inversionTime!=0:
            rfPulse(t0,rfReTime,rfReAmp,0)
        
        # Excitation pulse
        t0 += rfReTime/2+inversionTime-rfExTime/2
        rfPulse(t0,rfExTime,rfExAmp,drfPhase*np.pi/180)
    
        # Dephasing readout
        t0 += blkTime+rfExTime-gradDelay
        if repeIndex>=dummyPulses:         # This is to account for dummy pulses
            gradTrap(t0, acqTime+2*addRdGradTime, rdGradAmplitude/2*rdPreemphasis, axes[0])
        
        # First readout to avoid RP initial readout effect
#        if repeIndex==0:         # This is to account for dummy pulses
#            rxGate(t0+gradDelay+deadTime, acqTime+2*addRdPoints/BW)
        
        # Echo train
        for echoIndex in range(etl):
            # Refocusing pulse
            if echoIndex == 0:
                t0 += (-rfExTime+echoSpacing-rfReTime)/2-blkTime
            else:
                t0 += gradDelay-acqTime/2+echoSpacing/2-rfReTime/2-blkTime-addRdGradTime
            rfPulse(t0, rfReTime, rfReAmp, np.pi/2)

            # Dephasing phase and slice gradients
            t0 += blkTime+rfReTime
            if repeIndex>=dummyPulses:         # This is to account for dummy pulses
                gradTrap(t0, phaseGradTime, phGradients[phIndex], axes[1])
                gradTrap(t0, phaseGradTime, slGradients[slIndex], axes[2])
            
            # Readout gradient
            t0 += -rfReTime/2+echoSpacing/2-acqTime/2-gradRiseTime-gradDelay-addRdGradTime
            if repeIndex>=dummyPulses:         # This is to account for dummy pulses
                gradTrap(t0, acqTime+2*addRdGradTime, rdGradAmplitude, axes[0])

            # Rx gate
            t0 += gradDelay+gradRiseTime+addRdGradTime-addRdPoints/BW
            if repeIndex>=dummyPulses:         # This is to account for dummy pulses
                rxGate(t0, acqTime+2*addRdPoints/BW)

            # Rephasing phase and slice gradients
            t0 += addRdPoints/BW+acqTime-gradDelay+addRdGradTime
            if (echoIndex<etl-1 and repeIndex>=dummyPulses):
                gradTrap(t0, phaseGradTime, -phGradients[phIndex], axes[1])
                gradTrap(t0, phaseGradTime, -slGradients[slIndex], axes[2])

            # Update the phase and slice gradient
            if repeIndex>=dummyPulses:
                if phIndex == nPH-1:
                    phIndex = 0
                    slIndex += 1
                else:
                    phIndex += 1
            
            if phIndex == nPH-1 and slIndex == nSL-1:
                endSequence(scanTime)
    
    # Plot sequence:
#    expt.plot_sequence()
#    plt.show()
    
    # Run the experiment
    dataFull = []
    for ii in range(nScans):
        rxd, msgs = expt.run()
        rxd['rx0'] = rxd['rx0']*13.788   # Here I normalize to get the result in mV
        # Get data
        scanData = sig.decimate(rxd['rx0'], oversamplingFactor, ftype='fir', zero_phase=True)
        dataFull = np.concatenate((dataFull, scanData), axis = 0)
    
    # Get index for krd = 0
    # Average data
    dataProv = np.reshape(dataFull, (nScans, nRD*nPH*nSL))
    dataProv = np.average(dataProv, axis=0)
    dataProv = np.reshape(dataProv, (nSL, nPH, nRD))
    # Reorganize the data acording to sweep mode
    dataTemp = dataProv*0
    for ii in range(nPH):
        dataTemp[:, ind[ii], :] = dataProv[:,  ii, :]
    dataProv = dataTemp
    # Check where is krd = 0
    dataProv = dataProv[int(nSL/2), int(nPH/2), :]
    indkrd0 = np.argmax(np.abs(dataProv))

    # Get required readout points
    dataFull = np.reshape(dataFull, (nPH*nSL*nScans, nRD))
    dataFull = dataFull[:, indkrd0-int(nPoints[0]/2):indkrd0+int(nPoints[0]/2)]
    dataFull = np.reshape(dataFull, (1, nPoints[0]*nPH*nSL*nScans))
    
    # Average data
    data = np.reshape(dataFull, (nScans, nPoints[0]*nPH*nSL))
    data = np.average(data, axis=0)
    data = np.reshape(data, (nSL, nPH, nPoints[0]))
    
    # Reorganize the data acording to sweep mode
    dataTemp = data*0
    for ii in range(nPH):
        dataTemp[:, ind[ii], :] = data[:,  ii, :]
    
    # Do zero padding
    data = np.zeros((nPoints[2], nPoints[1], nPoints[0]))
    data = data+1j*data
    if nSL==1:
        data = dataTemp
    else:
        data[0:nSL-1, :, :] = dataTemp[0:nSL-1, :, :]
    data = np.reshape(data, (1, nPoints[0]*nPoints[1]*nPoints[2]))
        
    # Fix the position of the sample according t dfov
    kMax = nPoints/(2*fov)*axesEnable
    kRD = np.linspace(-kMax[0],kMax[0],num=nPoints[0],endpoint=False)
    kPH = np.linspace(-kMax[1],kMax[1],num=nPH,endpoint=False)
    kSL = np.linspace(-kMax[2],kMax[2],num=nSL,endpoint=False)
    kPH = kPH[::-1]
    kPH, kSL, kRD = np.meshgrid(kPH, kSL, kRD)
    kRD = np.reshape(kRD, (1, nPoints[0]*nPH*nSL))
    kPH = np.reshape(kPH, (1, nPoints[0]*nPH*nSL))
    kSL = np.reshape(kSL, (1, nPoints[0]*nPH*nSL))
    dPhase = np.exp(-2*np.pi*1j*(dfov[0]*kRD+dfov[1]*kPH+dfov[2]*kSL))
    data = data*dPhase
    
    # Create sampled data
    kRD = np.reshape(kRD, (nPoints[0]*nPoints[1]*nPoints[2], 1))
    kPH = np.reshape(kPH, (nPoints[0]*nPoints[1]*nPoints[2], 1))
    kSL = np.reshape(kSL, (nPoints[0]*nPoints[1]*nPoints[2], 1))
    data = np.reshape(data, (nPoints[0]*nPoints[1]*nPoints[2], 1))
    auxiliar['kMax'] = kMax
    outputs['sampled'] = np.concatenate((kRD, kPH, kSL, data), axis=1)

    # Get image with FFT
    data = np.reshape(data, (nSL, nPH, nPoints[0]))
    img=np.fft.ifftshift(np.fft.ifftn(data))
    outputs['image'] = img
    
    # Save data
    dt = datetime.now()
    dt_string = dt.strftime("%Y.%m.%d.%H.%M.%S")
    dt2 = date.today()
    dt2_string = dt2.strftime("%Y.%m.%d")
    if not os.path.exists('experiments/acquisitions/%s' % (dt2_string)):
        os.makedirs('experiments/acquisitions/%s' % (dt2_string))
            
    if not os.path.exists('experiments/acquisitions/%s/%s' % (dt2_string, dt_string)):
        os.makedirs('experiments/acquisitions/%s/%s' % (dt2_string, dt_string)) 
    inputs['name'] = "%s.%s.mat" % ("TSE",dt_string)
    rawData['inputs'] = inputs
    rawData['auxiliar'] = auxiliar
    rawData['outputs'] = outputs
    rawdata = {}
    rawdata['rawData'] = rawData
    savemat("experiments/acquisitions/%s/%s/%s.%s.mat" % (dt2_string, dt_string, "RARE",dt_string),  rawdata)

    # Plot provisional image
    plt.figure(1)
    tVector = np.linspace(-acqTime/2, acqTime/2, num=nPoints[0],endpoint=True)*1e-3
    for ii in range(nPH):
        plt.subplot(1, 2, 1)
        plt.plot(tVector, np.abs(data[0, ii, :]))
        plt.title("Signal amplitude")
        plt.xlabel("Time (ms)")
        plt.ylabel("Amplitude (mV)")
        plt.subplot(1, 2, 2)
        angle = np.unwrap(np.angle(data[0, ii, :]))
        plt.title("Signal phase")
        plt.xlabel("Time (ms)")
        plt.ylabel("Phase (rad)")
        plt.plot(tVector, angle)
    
    # Print larmor frequency
    if axesEnable[0]==0:
        dPhi = angle[-1]-angle[0]
        df = dPhi/(2*np.pi*acqTime)
        print("f0 = %s MHz" % (larmorFreq+df))
    
    # Plot data for 1D case
    if (nPH==1 and nSL==1):
        # Plot k-space
        plt.figure(2)
        dataPlot = data[0, 0, :]
        plt.subplot(1, 2, 1)
        if axesEnable[0]==0:
            tVector = np.linspace(-acqTime/2, acqTime/2, num=nPoints[0],endpoint=False)*1e-3
            sMax = np.max(np.abs(dataPlot))
            indMax = np.argmax(np.abs(dataPlot))
            timeMax = tVector[indMax]
            sMax3 = sMax/3
            dataPlot3 = np.abs(np.abs(dataPlot)-sMax3)
            indMin = np.argmin(dataPlot3)
            timeMin = tVector[indMin]
            T2 = np.abs(timeMax-timeMin)
            plt.plot(tVector, np.abs(dataPlot))
            plt.plot(tVector, np.real(dataPlot))
            plt.plot(tVector, np.imag(dataPlot))
            plt.xlabel('t (ms)')
            plt.ylabel('Signal (mV)')
            print("T2 = %s us" % (T2))
        else:
            plt.plot(kRD[0, :], np.abs(dataPlot))
            plt.yscale('log')
            plt.xlabel('krd (mm^-1)')
            plt.ylabel('Signal (mV)')
        # Plot image
        plt.subplot(122)
        img = img[0, 0, :]
        if axesEnable[0]==0:
            xAxis = np.linspace(-BW/2, BW/2, num=nPoints[0], endpoint=False)*1e3
            plt.plot(xAxis, np.abs(img), '.')
            plt.xlabel('Frequency (kHz)')
            plt.ylabel('Density (a.u.)')
            print("Smax = %s mV" % (np.max(np.abs(img))))
        else:
            xAxis = np.linspace(-fov[0]/2*1e2, fov[0]/2*1e2, num=nPoints[0], endpoint=False)
            plt.plot(xAxis, np.abs(img))
            plt.xlabel('Position RD (cm)')
            plt.ylabel('Density (a.u.)')
    else:
        # Plot k-space
        plt.figure(2)
        dataPlot = data[round(nSL/2), :, :]
        plt.subplot(121)
        plt.imshow(np.log(np.abs(dataPlot)),cmap='gray')
        plt.axis('off')
        # Plot image
        if sweepMode==3:
            imgPlot = img[round(nSL/2), round(nPH/4):round(3*nPH/4), :]
        else:
            imgPlot = img[round(nSL/2), :, :]
        plt.subplot(122)
        plt.imshow(np.abs(imgPlot), cmap='gray')
        plt.axis('off')
        plt.title("RARE.%s.mat" % (dt_string))
    
    # Delete experiment:
    expt.__del__()
    
    plt.show()
    

#*********************************************************************************
#*********************************************************************************
#*********************************************************************************


def getIndex(g_amps, echos_per_tr, n_ph, sweep_mode):
    n2ETL=np.int32(n_ph/2/echos_per_tr)
    ind:np.int32 = [];
    if n_ph==1:
         ind = np.linspace(np.int32(n_ph)-1, 0, n_ph)
    
    else: 
        if sweep_mode==0:   # Sequential for T2 contrast
            for ii in range(np.int32(n_ph/echos_per_tr)):
               ind = np.concatenate((ind, np.arange(1, n_ph+1, n_ph/echos_per_tr)+ii))
            ind = ind-1

        elif sweep_mode==1: # Center-out for T1 contrast
            if echos_per_tr==n_ph:
                for ii in range(np.int32(n_ph/2)):
                    cont = 2*ii
                    ind = np.concatenate((ind, np.array([n_ph/2-cont/2])), axis=0);
                    ind = np.concatenate((ind, np.array([n_ph/2+1+cont/2])), axis=0);
            else:
                for ii in range(n2ETL):
                    ind = np.concatenate((ind,np.arange(n_ph/2, 0, -n2ETL)-(ii)), axis=0);
                    ind = np.concatenate((ind,np.arange(n_ph/2+1, n_ph+1, n2ETL)+(ii)), axis=0);
            ind = ind-1
        elif sweep_mode==2: # Out-to-center for T2 contrast
            if echos_per_tr==n_ph:
                ind=np.arange(1, n_ph+1, 1)
            else:
                for ii in range(n2ETL):
                    ind = np.concatenate((ind,np.arange(1, n_ph/2+1, n2ETL)+(ii)), axis=0);
                    ind = np.concatenate((ind,np.arange(n_ph, n_ph/2, -n2ETL)-(ii)), axis=0);
            ind = ind-1
        elif sweep_mode==3:
            if echos_per_tr==n_ph:
                ind = np.arange(0, n_ph, 1)
            else:
                for ii in range(int(n2ETL)):
                    ind = np.concatenate((ind, np.arange(0, n_ph, 2*n2ETL)+2*ii), axis=0)
                    ind = np.concatenate((ind, np.arange(n_ph-1, 0, -2*n2ETL)-2*ii), axis=0)

    return np.int32(ind)


#*********************************************************************************
#*********************************************************************************
#*********************************************************************************


def reorganizeGfactor(axes):
    gFactor = np.array([0., 0., 0.])
    
    # Set the normalization factor for readout, phase and slice gradient
    for ii in range(3):
        if axes[ii]==0:
            gFactor[ii] = Gx_factor
        elif axes[ii]==1:
            gFactor[ii] = Gy_factor
        elif axes[ii]==2:
            gFactor[ii] = Gz_factor
    
    return(gFactor)

#*********************************************************************************
#*********************************************************************************
#*********************************************************************************


if __name__ == "__main__":

    rare_standalone()