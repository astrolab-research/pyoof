#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Tomas Cassanelli
import numpy as np
import os
from astropy.time import Time
from astropy import units as apu
from astropy.constants import c as light_speed
from astropy.io import fits
from .aperture import radiation_pattern

__all__ = ['simulate_data_pyoof', "simulate_data_pyoof_multifreq"]

def simulate_data_pyoof_multifreq( I_coeff, K_coeff, wavel_array, d_z, illum_func, telgeo, noise, resolution,
    box_factor, work_dir=None):
    if work_dir is None:
        work_dir = os.getcwd()
    fits_files = []
    fits_paths = []
    for wavel in wavel_array:
        fits_names = "fits_wavel_{}".format(wavel)
        fits_files.append(simulate_data_pyoof(I_coeff, K_coeff, wavel, d_z, illum_func, telgeo, noise, resolution, box_factor, fits_name = fits_names))
        name_file = os.path.join(work_dir, 'data_generated', fits_names + '.fits')
        fits_paths.append(name_file)
    return fits_files, fits_paths


def simulate_data_pyoof(
    I_coeff, K_coeff, wavel, d_z, illum_func, telgeo, noise, resolution,
    box_factor, work_dir=None, fits_name = "test", overwrite = True
        ):
    """
    Routine to generate data and test the pyoof package algorithm. It has the
    default setting for the pyoof FITS file input.

    Parameters
    ----------
    I_coeff : `list`
        List which contains 4 parameters, the illumination amplitude,
        :math:`A_{E_\\mathrm{a}}`, the illumination taper,
        :math:`c_\\mathrm{dB}` and the two coordinate offset, :math:`(x_0,
        y_0)`. The illumination coefficients must be listed as follows,
        ``I_coeff = [i_amp, c_dB, x0, y0]``.
    K_coeff : `~numpy.ndarray`
        Constants coefficients, :math:`K_{n\\ell}`, for each of them there is
        only one Zernike circle polynomial, :math:`U^\\ell_n(\\varrho,
        \\varphi)`.
    wavel : `~astropy.units.quantity.Quantity`
        Wavelength, :math:`\\lambda`, of the observation in length units.
    d_z : `~astropy.units.quantity.Quantity`
        Radial offset :math:`d_z`, added to the sub-reflector in length units.
        This characteristic measurement adds the classical interference
        pattern to the beam maps, normalized squared (field) radiation
        pattern, which is an out-of-focus property. The radial offset list
        must be as follows, ``d_z = [d_z-, 0., d_z+]`` all of them in length
        units.
    illum_func : `function`
        Illumination function, :math:`E_\\mathrm{a}(x, y)`, to be evaluated
        with the key ``I_coeff``. The illumination functions available are
        `~pyoof.aperture.illum_parabolic` and `~pyoof.aperture.illum_gauss`.
    telgeo : `list`
        List that contains the blockage distribution, optical path difference
        (OPD) function, and the primary radius (`float`) in lenght units. The
        list must have the following order, ``telego = [block_dist, opd_func,
        pr]``.
    noise : `float`
        Noise amplitude added to the generated data. The noise comes from a
        random Gaussian, see `~numpy.random.normal`.
    resolution : `int`
        Fast Fourier Transform resolution for a rectangular grid. The input
        value has to be greater or equal to the telescope resolution and with
        power of 2 for faster FFT processing. It is recommended a value higher
        than ``resolution = 2 ** 8``.
    box_factor : `int`
        Related to the FFT resolution (**resolution** key), defines the image
        pixel size level. It depends on the primary radius, ``pr``, of the
        telescope, e.g. a ``box_factor = 5`` returns ``x = np.linspace(-5 *
        pr, 5 * pr, resolution)``, an array to be used in the FFT2
        (`~numpy.fft.fft2`).
    work_dir : `str`
        Default is `None`, it will store the FITS file in the current
        directory, for other provide the desired path.

    Returns
    -------
    pyoof_fits : `~astropy.io.fits.hdu.hdulist.HDUList`
        The output fits file is stored in the directory ``'data_generated/'``.
        Every time the function is executed a new file will be stored (with
        increased numbering). The file is ready to use for the `~pyoof`
        package.

    Raises
    ------
    `ValueError`
        If the known a priori radial offset ``d_z`` is different than:
        ``[d_z-, 0., d_z+]``, negative, zero, and positive float.
    """
    print("simulation wavel: {}".format(wavel))

    #if (d_z[0] > 0) or (d_z[1] != 0) or (d_z[2] < 0):
    #    raise ValueError(
    #        "Radial offset must match: [d_z-, 0., d_z+] convention"
    #        )

    if work_dir is None:
        work_dir = os.getcwd()

    freq = light_speed / wavel
    bw = 1.22 * apu.rad * wavel / (2 * telgeo[2])  # beamwidth in radians
    size_in_bw = 8 * bw

    plim = [
        -size_in_bw.to_value(apu.rad), size_in_bw.to_value(apu.rad),
        -size_in_bw.to_value(apu.rad), size_in_bw.to_value(apu.rad)
        ] * apu.rad
    plim_u, plim_v = plim[:2], plim[2:]

    # Generating power pattern and spatial frequencies
    u, v, P = [], [], []
    for i in range(len(d_z)):
        _u, _v, _radiation = radiation_pattern(
            K_coeff=K_coeff,
            I_coeff=I_coeff,
            d_z=d_z[i],
            wavel=wavel,
            illum_func=illum_func,
            telgeo=telgeo,
            resolution=resolution,
            box_factor=box_factor
            )

        uu, vv = np.meshgrid(_u, _v)
        power_pattern = np.abs(_radiation) ** 2

        # trim the power pattern
        power_pattern[(plim_u[0] > uu)] = np.nan
        power_pattern[(plim_u[1] < uu)] = np.nan
        power_pattern[(plim_v[0] > vv)] = np.nan
        power_pattern[(plim_v[1] < vv)] = np.nan

        power_trim_1d = power_pattern[~np.isnan(power_pattern)]
        size_trim = int(np.sqrt(power_trim_1d.size))  # new size of the box

 
        # Box to be trimmed in uu and vv meshed arrays
        box = (
            (plim_u[0] < uu) & (plim_u[1] > uu) &
            (plim_v[0] < vv) & (plim_v[1] > vv)
            )

        # reshaping trimmed arrys
        power_trim = power_trim_1d.reshape(size_trim, size_trim)
        u_trim = uu[box].reshape(size_trim, size_trim)
        v_trim = vv[box].reshape(size_trim, size_trim)
        print(power_trim.shape)
        u.append(u_trim)
        v.append(v_trim)
        P.append(power_trim)

    # adding noise!
    if noise == 0:
        power_noise = np.array(P)
    else:
        power_noise = (
            np.array(P) +
            np.random.normal(0., noise, np.array(P).shape)
            )

    u_to_save = [u[i].to_value(apu.rad).flatten() for i in range(len(d_z))]
    v_to_save = [v[i].to_value(apu.rad).flatten() for i in range(len(d_z))]
    p_to_save = [power_noise[i].flatten() for i in range(len(d_z))]
    p_no_noise_to_save = [P[i].flatten() for i in range(len(d_z))]

    # Writing default fits file for OOF observations
    hdu_tables = []
    for i in range(len(d_z)):
        table_hdu = fits.BinTableHDU.from_columns([
        fits.Column(name='U', format='E', array=u_to_save[i]),
        fits.Column(name='V', format='E', array=v_to_save[i]),
        fits.Column(name='BEAM', format='E', array=p_to_save[i]),
        fits.Column(name = 'POWER', format ='E', array=p_no_noise_to_save[i])
        ])
        hdu_tables.append(table_hdu)

    #table_hdu0 = fits.BinTableHDU.from_columns([
    #    fits.Column(name='U', format='E', array=u_to_save[0]),
    #    fits.Column(name='V', format='E', array=v_to_save[0]),
    #    fits.Column(name='BEAM', format='E', array=p_to_save[0])
    #    ])

    #table_hdu1 = fits.BinTableHDU.from_columns([
    #    fits.Column(name='U', format='E', array=u_to_save[1]),
    #    fits.Column(name='V', format='E', array=v_to_save[1]),
    #    fits.Column(name='BEAM', format='E', array=p_to_save[1])
    #    ])

    #table_hdu2 = fits.BinTableHDU.from_columns([
    #    fits.Column(name='U', format='E', array=u_to_save[2]),
    #    fits.Column(name='V', format='E', array=v_to_save[2]),
    #    fits.Column(name='BEAM', format='E', array=p_to_save[2])
    #    ])

    # storing data
    if not os.path.exists(os.path.join(work_dir, 'data_generated')):
        os.makedirs(os.path.join(work_dir, 'data_generated'))
    
    name_file = os.path.join(work_dir, 'data_generated', fits_name + '.fits')

    prihdr = fits.Header()
    prihdr['FREQ'] = freq.to_value(apu.Hz)
    prihdr['WAVEL'] = wavel.to_value(apu.m)
    prihdr['MEANEL'] = 0
    prihdr['OBJECT'] = name_file
    prihdr['DATE_OBS'] = Time.now().isot
    prihdr['COMMENT'] = 'Generated data pyoof package'
    prihdr['AUTHOR'] = 'Tomas Cassanelli'
    prihdr['NMAPS'] = len(d_z)
    prihdr['NOISE'] = noise
    prihdu = fits.PrimaryHDU(header=prihdr)

    pyoof_fits = fits.HDUList(
        [prihdu] + hdu_tables
        )
    #print("aaaaaaaaaaaa")
    for i in range(1, len(d_z)+1):
        #print("i:{},    d_z[i]:{}".format(i, d_z[i-1].to_value(apu.m)))
        pyoof_fits[i].header['DZ'] = d_z[i-1].to_value(apu.m)
        pyoof_fits[i].name = 'MINUS OOF'
    pyoof_fits.writeto(name_file, overwrite = overwrite)

    return pyoof_fits
