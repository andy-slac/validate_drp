#!/bin/bash

# Setup
export OMP_NUM_THREADS=1

# Fake out the pipeline about the origin of the reference catalog
export SETUP_ASTROMETRY_NET_DATA="astrometry_net_data sdss-dr9-fink-v5b"
export ASTROMETRY_NET_DATA_DIR=${CI_HSC_DIR}/sdss-dr9-fink-v5b

REPO='DATA'
RERUN=20161216

# DATA_DIR=${VALIDATION_DATA_HSC_DIR}
DATA_DIR=${CI_HSC_DIR}
CALIB_DIR=${CI_HSC_DIR}/CALIB

# Ingest raw data into repo
mkdir -p ${REPO}
ln -s ${CALIB_DIR} ${REPO}/CALIB
echo lsst.obs.hsc.HscMapper > ${REPO}/_mapper
ingestImages.py ${REPO} --mode=link ${CI_HSC_DIR}/'raw/*.fits'

# ALL_VISITS=903982^904006^904828^904846^903332^903340^904350^904378
# ALL_VISITS=90333426^90333828^90334738^90398825^90401136^90333427^90334231^90334744^90398826^90401142^90333430^90334336^90334754^90398829^90401538^90333431^90334342^90398626^90398830^90401544^90333625^90334537^90398627^90399024^90401554^90333629^90334543^90398630^90399028^90333824^90334553^90398631^90401031
ALL_VISITS=903334^903338^903347^903988^904011^903334^903342^903347^903988^904011^903334^903343^903347^903988^904015^903334^903343^903986^903988^904015^903336^903345^903986^903990^904015^903336^903345^903986^903990^903338^903345^903986^90401031

# Heavy lifting
singleFrameDriver.py ${REPO} --calib ${CALIB_DIR} --rerun ${RERUN} --job singleFrame --cores 16 --id visit=${ALL_VISITS}
makeDiscreteSkyMap.py ${REPO} --rerun ${RERUN} --id ccd=0..103 visit=${ALL_VISITS}
# makeDiscreteSkyMap: tract 0 has corners (321.714, -1.294), (318.915, -1.294), (318.915, 1.504), (321.714, 1.504) (RA, Dec deg) and 15 x 15 patches
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-I --selectId ccd=0..103 visit=903982^904006^904828^904846
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-R --selectId ccd=0..103 visit=903332^903340
### coaddDriver.py ${REPO} --rerun ${RERUN} --job coadd --cores 16 --id tract=0 filter=HSC-Y --selectId ccd=0..103 visit=904350^904378
### multiBandDriver.py ${REPO} --rerun ${RERUN} --job multiband --cores 16 --id tract=0 filter=HSC-R^HSC-I^HSC-Y -C multiband-config.py
