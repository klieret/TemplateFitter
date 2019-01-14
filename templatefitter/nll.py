"""This module contains definitions for different likelihood
functions which are used as const function to be minimized in
the fit.
"""
from abc import ABC, abstractmethod, abstractproperty

import logging
import itertools
import numpy as np

from scipy.linalg import block_diag

__all__ = [
    "AbstractTemplateCostFunction",
    "AdvancedPoissonNegativeLogLikelihood",
    "SimplePoissonNegativeLogLikelihood"
]

logging.getLogger(__name__).addHandler(logging.NullHandler())

class AbstractTemplateCostFunction(ABC):
    """Abstract base class for all cost function to estimate
    yields using the template method.

    Parameters
    ----------
    hdata : Histogram
        Bin counts of the data histogram. Shape is (nbins,).
    templates : Implementation of an AbstractCompositeTemplate
        A CompositeTemplate instance. The templates are used to
        extract the contribution from each process described by
        the templates to the measured data set.
    """

    def __init__(self, hdata, templates):
        self._data = hdata
        self._templates = templates

    # -- properties --

    @property
    def x0(self):
        """numpy.ndarray: Starting values for the minimization."""
        return self._templates.yield_values

    # -- abstract properties

    @abstractproperty
    def param_names(self):
        pass

    # -- abstract methods --

    @abstractmethod
    def __call__(self, x):
        pass


class SimplePoissonNegativeLogLikelihood(AbstractTemplateCostFunction):
    """A negative log likelihood (NLL) function for binned data using
    template histograms shapes as pdfs. The NLL is calculated as

    :math:`-\log(L) = \sum\limits_{i=1}^{n_{\mathrm{bins}}} \\nu_i - n_i \log(\\nu_i)`,

    with:

    * :math:`\\nu_i` - total expected number of events in bin :math:`i`
    * :math:`n_i` - measured number of events in bin :math:`i`.

    The total expected number of events per bin is given by

    :math:`\\nu_i = \sum\limits_{k=1}^{n_\mathrm{templates}} f_{ik}\\nu_{ik}`,

    with:

    * :math:`\\nu_{ik}` - expected number of events in bin :math:`i` of template :math:`k`
    * :math:`f_{ik}` - fraction of template :math:`k` in bin :math:`i`.

    :math:`f_{ik} = \frac{\\nu_{ik}}{\sum\limits_{j=1}^{n_\mathrm{bins}}\\nu_{jk}}.

    Parameters
    ----------
    hdata : Histogram
        Bin counts of the data histogram. Shape is (nbins,).
    templates : AdvancedCompositeTemplate
        A CompositeTemplate instance. The templates are used to
        extract the contribution from each process described by
        the templates to the measured data set.
    """

    def __init__(self, hdata, templates):
        super().__init__(hdata, templates)

    @property
    def param_names(self):
        return [ "yield_" + template for template in self._templates.template_ids]

    def __call__(self, x):
        """This function is called by the minimize method.
        `x` is an 1-D array with shape (n,). These are the parameters
        which are fitted.

        Returns
        -------
        float
            The value of the negative log likelihood at `x`.
        """
        poi = x

        exp_evts_per_bin = poi @ self._templates.bin_fractions()
        poisson_term = np.sum(
            exp_evts_per_bin - self._data.bin_counts * np.log(exp_evts_per_bin)
        )

        return poisson_term


class AdvancedPoissonNegativeLogLikelihood(AbstractTemplateCostFunction):
    """A negative log likelihood (NLL) function for binned data using
    template histograms shapes as pdfs. The NLL is calculated as

    :math:`-\log(L) = \sum\limits_{i=1}^{n_{\mathrm{bins}}} \\nu_i - n_i \log(\\nu_i)`,

    with:
 
    * :math:`\\nu_i` - total expected number of events in bin :math:`i`
    * :math:`n_i` - measured number of events in bin :math:`i`.

    The total expected number of events per bin is given by

    :math:`\\nu_i = \sum\limits_{k=1}^{n_\mathrm{templates}} f_{ik}\\nu_{ik}`,

    with:

    * :math:`\\nu_{ik}` - expected number of events in bin :math:`i` of template :math:`k`
    * :math:`f_{ik}` - fraction of template :math:`k` in bin :math:`i`.

    :math:`f_{ik} does depend on a nuissance parameter :math:`\theta_{ik}`:

    :math:`f_{ik} = \frac{\\nu_{ik}(1 + \theta_{ik}\epsilon{ik})}{\sum\limits_{j=1}^{n_\mathrm{bins}}\\nu_{jk}(1 + \theta_{jk}\epsilon{jk})},

    where :math:`\epsilon_{jk}` is the relative uncertainty of template
    :math:`k` in bin :math:`j`.

    Parameters
    ----------
    hdata : Histogram
        Bin counts of the data histogram. Shape is (nbins,).
    composite_template : AdvancedCompositeTemplate
        A CompositeTemplate instance. The templates are used to
        extract the contribution from each process described by
        the templates to the measured data set.
    """

    def __init__(self, hdata, templates):
        super().__init__(hdata, templates)
        self._block_diag_inv_corr_mats = block_diag(*self._templates.inv_corr_mats)

    @property
    def x0(self):
        initial_yields = self._templates.yield_values
        inital_nuissance_params = self._templates.nuiss_param_values

        return np.concatenate((initial_yields, inital_nuissance_params))

    @property
    def param_names(self):
        yields = ["yield_" + template_id for template_id in self._templates.template_ids]
        nuissance_params = [["theta_" + template_name + f"_{i}" for i in range(self._templates.num_bins)]
                            for template_name in self._templates.template_ids]
        yields.extend(itertools.chain.from_iterable(nuissance_params))
        return yields

    def __call__(self, x):
        """This function is called by the minimize method.
        `x` is an 1-D array with shape (n,). These are the parameters
        which are fitted.

        Returns
        -------
        float
            The value of the negative log likelihood at `x`.
        """
        poi = x[:self._templates.num_templates]
        nuiss_params = x[self._templates.num_templates:]

        exp_evts_per_bin = poi @ self._templates.bin_fractions(
                nuiss_params
        )
        poisson_term = np.sum(
            exp_evts_per_bin - self._data.bin_counts * np.log(exp_evts_per_bin)
                              )

        gauss_term = 0.5*(nuiss_params@self._block_diag_inv_corr_mats@nuiss_params)
        return poisson_term + gauss_term



