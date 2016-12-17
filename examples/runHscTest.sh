#!/bin/bash

# Setup
export OMP_NUM_THREADS=1

# Fake out the pipeline about the origin of the reference catalog
export SETUP_ASTROMETRY_NET_DATA="astrometry_net_data sdss-dr9-fink-v5b"
export ASTROMETRY_NET_DATA_DIR=`pwd`/sdss-dr9-fink-v5b

REPO='DATA'
RERUN=20161216

# Ingest raw data into repo
mkdir ${REPO}
echo lsst.obs.hsc.HscMapper > ${REPO}/_mapper
ingestImages.py ${REPO} --mode=link ${VALIDATION_DATA_HSC_DIR}/'raw/*.fits'

# Heavy lifting
singleFrameDriver.py ${REPO} --calib CALIB --rerun ${RERUN} --job singleFrame --cores 16 --id ccd=0..103 visit=903982^904006^904828^904846^903332^903340^904350^904378
makeDiscreteSkyMap.py ${REPO} --rerun ${RERUN} --id ccd=0..103 visit=903982^904006^904828^904846^903332^903340^904350^904378
# makeDiscreteSkyMap: tract 0 has corners (321.714, -1.294), (318.915, -1.294), (318.915, 1.504), (321.714, 1.504) (RA, Dec deg) and 15 x 15 patches
coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-I --selectId ccd=0..103 visit=903982^904006^904828^904846
coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-R --selectId ccd=0..103 visit=903332^903340
coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-Y --selectId ccd=0..103 visit=904350^904378
multiBandDriver.py ${REPO} --rerun ${RERUN} --job multiband --cores 16 --id tract=0 filter=HSC-R^HSC-I^HSC-Y -C multiband-config.py
