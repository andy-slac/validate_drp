#!/bin/bash

# Setup
export OMP_NUM_THREADS=1

# Fake out the pipeline about the origin of the reference catalog
export SETUP_ASTROMETRY_NET_DATA="astrometry_net_data sdss-dr9-fink-v5b"
export ASTROMETRY_NET_DATA_DIR=${VALIDATION_DATA_HSC_DIR}/sdss-dr9-fink-v5b

REPO='DATA'
RERUN=20170103

DATA_DIR=${VALIDATION_DATA_HSC_DIR}
CALIB_DIR=${VALIDATION_DATA_HSC_DIR}/CALIB

# Ingest raw data into repo
mkdir -p ${REPO}
ln -s ${CALIB_DIR} ${REPO}/CALIB
echo lsst.obs.hsc.HscMapper > ${REPO}/_mapper
ingestImages.py ${REPO} --mode=link ${VALIDATION_DATA_HSC_DIR}/'raw/*.fits'

ALL_VISITS=903332^903333^903340^903341^903982^903983^904006^904007^904350^904351^904378^904379^904828^904829^904846^904847

# Heavy lifting
singleFrameDriver.py ${REPO} --calib ${CALIB_DIR} --rerun ${RERUN} --job singleFrame --cores 16 --id visit=${ALL_VISITS}
makeDiscreteSkyMap.py ${REPO} --rerun ${RERUN} --id ccd=0..103 visit=${ALL_VISITS}
# makeDiscreteSkyMap INFO: tract 0 has corners (321.714, -1.294), (318.915, -1.294), (318.915, 1.504), (321.714, 1.504) (RA, Dec deg) and 15 x 15 patches

coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-I --selectId ccd=0..103 visit=903982^904006^904828^904846
coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-R --selectId ccd=0..103 visit=903332^903340
coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-Y --selectId ccd=0..103 visit=904350^904378
multiBandDriver.py ${REPO} --rerun ${RERUN} --job multiband --cores 16 --id tract=0 filter=HSC-R^HSC-I^HSC-Y -C multiband-config.py
