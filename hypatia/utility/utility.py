# -*- coding: utf-8 -*-

"""
This module contains the utility functions from cerating the optimization problem
"""

import cvxpy as cp
import numpy as np
import pandas as pd


def stack(a, b, axis=0):

    """
    concat cvxpy variable rows or columns
    """

    if axis == 0:
        return cp.vstack([a, b])
    elif axis == 1:
        return cp.hstack([a, b])

def shift_new_cap(newcap,techs, toc, years):
    
    new_capacity = []
    for indx, tech in enumerate(techs):
        shift = cp.reshape(newcap[:-toc.iloc[:,indx].values[0],indx], 
                            (newcap[:-toc.iloc[:,indx].values[0],indx].shape[0],1))
        non_var = np.zeros((toc.iloc[:,indx].values[0],1))
        new_capacity.append(cp.vstack([non_var,shift]))
    real_new_capacity_regional =cp.hstack(new_capacity)
    
    
    return real_new_capacity_regional

def shift_new_line_cap(newlinecap,carrier, toc, years):
    
    line_new_capacity = []
    for indx, carr in enumerate(carrier):
        shift_line = cp.reshape(newlinecap[:-toc.iloc[:,indx].values[0],indx], 
                            (newlinecap[:-toc.iloc[:,indx].values[0],indx].shape[0],1))
        non_var = np.zeros((toc.iloc[:,indx].values[0],1))
        line_new_capacity.append(cp.vstack([non_var,shift_line]))
    real_new_line_capacity =cp.hstack(line_new_capacity)
    
    
    return real_new_line_capacity


def newcap_accumulated(newcap, techs, main_years, tlft):

    """
    Calculates the accumulated new capacity of each technology in each
    year of the model horizon based on the useful technical lifetime
    """

    index = pd.MultiIndex.from_product([techs, main_years])
    exist = pd.DataFrame(0, index=index, columns=index)

    newcap_reshape = cp.reshape(newcap, (len(main_years) * len(techs), 1))

    for tech in techs:
        for year in main_years:
            for year0 in main_years:

                age = main_years.index(year) - main_years.index(year0)

                if age >= 0 and age < tlft[tech].values:

                    exist.loc[(tech, year), (tech, year0)] = 1
    
    accumulated_newcap_reshape = exist.values @ newcap_reshape
    accumulated_newcap = cp.reshape(accumulated_newcap_reshape, newcap.shape)  


    return accumulated_newcap


def _calc_variable_overall(
    glob_technologies, regions, main_years, technologies, variable
):

    """
    Calculates the aggregated annual total or new capacity of each technology
    over all the regions
    """

    variable_overall = {}
    for tech in list(
        glob_technologies.loc[glob_technologies["Tech_category"] != "Demand"][
            "Technology"
        ]
    ):
        variable_overall[tech] = np.zeros((len(main_years), 1))
        for reg in regions:
            for key, value in technologies[reg].items():

                if tech in value:

                    variable_overall[tech] += variable[reg][key][:, value.index(tech)]

    return variable_overall


def _calc_production_overall(
    glob_technologies, regions, main_years, technologies, variable
):

    """
    Calculates the aggregated annual production of each technology
    over all the regions
    """

    production_overall = {}
    for tech in list(
        glob_technologies.loc[
            (glob_technologies["Tech_category"] != "Demand")
            & (glob_technologies["Tech_category"] != "Storage")
        ]["Technology"]
    ):
        production_overall[tech] = np.zeros((len(main_years), 1))
        for reg in regions:
            for key, value in technologies[reg].items():

                if tech in value:

                    production_overall[tech] += variable[reg][key][:, value.index(tech)]

    return production_overall

def _calc_carr_production_overall(
        glob_carriers, regions, main_years, carriers, variable
):
    
    """
    Calculates the aggregated annual production of each carrier
    over all the regions
    """
    
    production_overall = {}
    for carr in list(
            glob_carriers["Carrier"]
    ):
        production_overall[carr] = np.zeros((len(main_years), 1))
        for reg in regions:
            for key in carriers[reg]["Carrier_output"]["Carrier_out"]:

                if carr in key:

                    production_overall[carr] += variable[reg][key]

    return production_overall
    


def line_newcap_accumulated(line_newcap, carriers, main_years, line_tlft):

    """
    Calculates the accumulated new capacity of each inter-regional link in each
    year the model horizon based on the useful technical lifetime
    """

    index_line = pd.MultiIndex.from_product([carriers, main_years])
    exist_line = pd.DataFrame(0, index=index_line, columns=index_line)

    line_newcap_reshape = cp.reshape(line_newcap, (len(main_years) * len(carriers), 1))

    for carrier in carriers:
        for year in main_years:
            for year0 in main_years:

                age = main_years.index(year) - main_years.index(year0)

                if age >= 0 and age < line_tlft[carrier].values:

                    exist_line.loc[(carrier, year), (carrier, year0)] = 1

    line_newacp_accumulated_reshape = exist_line.values @ line_newcap_reshape

    line_newcap_accumulated = cp.reshape(
        line_newacp_accumulated_reshape, line_newcap.shape
    )

    return line_newcap_accumulated


def decomcap(newcap, techs, main_years, tlft):

    """
    Calculates the annual decomissioned capacity of each technology in each
    year of the time horizon based on life time of the new capacities
    installed in the vintage years
    """
    index = pd.MultiIndex.from_product([techs, main_years])
    decom_matrix = pd.DataFrame(0, index=index, columns=index)
    newcap_reshape = cp.reshape(newcap, (len(main_years) * len(techs), 1))

    for tech in techs:
        for indx, year in enumerate(main_years):

            try:

                decom_matrix.loc[
                    (tech, main_years[int(indx + tlft[tech].values)]), (tech, year)
                ] = 1

            except:
                pass

    decomcap_reshape = decom_matrix.values @ newcap_reshape
    decomcap = cp.reshape(decomcap_reshape, newcap.shape)
    return decomcap


def line_decomcap(line_newcap, carriers, main_years, line_tlft):

    """
    Calculates the annual decomissioned capacity of each inter-regional link in each
    year of the time horizon based on life time of the new capacities
    installed in the vintage years
    """

    index_line = pd.MultiIndex.from_product([carriers, main_years])
    decom_matrix_line = pd.DataFrame(0, index=index_line, columns=index_line)
    line_newcap_reshape = cp.reshape(line_newcap, (len(main_years) * len(carriers), 1))

    for carrier in carriers:
        for year in main_years:

            try:
                decom_matrix_line.loc[
                    (carrier, main_years[main_years.index(year) + line_tlft[carrier]]),
                    (carrier, year),
                ] = 1

            except:
                pass
    line_decomcap_reshape = decom_matrix_line.values @ line_newcap_reshape
    line_decomcap = cp.reshape(line_decomcap_reshape, line_newcap.shape)
    return line_decomcap


# annual undiscounted investmnests and their related taxes and subsidies


def invcosts(inv, newcap, inv_tax, inv_sub):

    """
    Calculates the annual undiscounted investment cost of each technology and
    their taxes and subsidies before considering the annuities
    """

    cost_inv = cp.multiply(inv.values, newcap)
    specific_inv_tax = cp.multiply(inv_tax.values, inv.values)
    specific_inv_sub = cp.multiply(inv_sub.values, inv.values)
    cost_inv_tax = cp.multiply(specific_inv_tax, newcap)
    cost_inv_sub = cp.multiply(specific_inv_sub, newcap)

    return cost_inv, cost_inv_tax, cost_inv_sub


def invcosts_annuity(
    cost_inv_present,
    interest_rate,
    economiclife,
    technologies,
    main_years,
    discount_rate,
):

    """
    Calculates the annuities of the investment costs based on the interest rate
    and economic lifetime of each technology
    """

    depreciation = np.divide(
        np.multiply(
            np.power((interest_rate.values + 1), economiclife.values),
            interest_rate.values,
        ),
        (np.power((interest_rate.values + 1), economiclife.values) - 1),
    )
    depreciation = pd.DataFrame(
        depreciation, index=["Depreciation_rate"], columns=technologies
    )

    inv_fvalue_total = 0
    for tech_indx, tech in enumerate(technologies):
        inv_fvalue_discounted = 0
        for y_indx, year in enumerate(main_years):

            inv_fvalue_annual_discounted = 0
            for future_year in range(
                y_indx + 1, y_indx + economiclife.loc["Economic Life time", tech] + 1
            ):

                annuity = (
                    cost_inv_present[y_indx, tech_indx]
                    * depreciation.loc["Depreciation_rate", tech]
                )

                inv_fvalue_annual_discounted += annuity * (
                    1 + discount_rate.loc[year, "Annual Discount Rate"]
                ) ** (-future_year)

            inv_fvalue_discounted += inv_fvalue_annual_discounted

        inv_fvalue_total += inv_fvalue_discounted

    return inv_fvalue_total


# annual undiscounted fixed O&M costs and their related taxes and subsidies


def fixcosts(fix, totalcap, fix_tax, fix_sub):

    """
    Calculates the annual undiscounted fixed operation and maintenance costs
    and their taxes and subsidies
    """

    cost_fix = cp.multiply(fix.values, totalcap)
    specific_fix_tax = cp.multiply(fix_tax.values, fix.values)
    specific_fix_sub = cp.multiply(fix_sub.values, fix.values)
    cost_fix_tax = cp.multiply(specific_fix_tax, totalcap)
    cost_fix_sub = cp.multiply(specific_fix_sub, totalcap)

    return cost_fix, cost_fix_tax, cost_fix_sub


def varcost(specific_varcost, activity, time_step):

    """
    Calculates the annual undiscounted variables costs
    """

    specific_varcost_reshape = pd.concat(
        [specific_varcost] * len(time_step)
    ).sort_index()
    variablecost = cp.multiply(specific_varcost_reshape.values, activity)

    return variablecost


def available_resource_prod(
    totalcap, capacity_factor, timeslice_fraction, annualprod_per_unitcapacity
):

    """
    Calculates the maximum available production due to the resource availability
    """

    available_capacity = cp.multiply(totalcap, capacity_factor)
    annualprod = cp.multiply(available_capacity, annualprod_per_unitcapacity)
    annual_prod_per_timslice = cp.multiply(annualprod, timeslice_fraction)

    return annual_prod_per_timslice


def annual_activity(activity, main_years, timeslices):

    """
    Calculates the annual production from the prodution defined on timeslices
    """
    
    activity_annual = cp.sum(activity[0 : len(timeslices), :], axis=0, keepdims=True)

    for indx, year in enumerate(main_years[1:]):

        activity_annual_rest = cp.sum(
            activity[(indx + 1) * len(timeslices) : (indx + 2) * len(timeslices), :],
            axis=0,
            keepdims=True,
        )
        activity_annual = stack(activity_annual, activity_annual_rest)

    return activity_annual


def line_varcost(
    specific_varcost, line_import, regions, main_years, time_slices, lines_list
):

    """
    Calculates the annual undiscounted variables costs of inter-regional links
    """

    variablecost_line = {}

    for reg in regions:

        variablecost_line_regional = {}

        for key, value in line_import[reg].items():

            line_import_anunual = annual_activity(value, main_years, time_slices)

            if "{}-{}".format(reg, key) in lines_list:

                specific_varcost_line = specific_varcost.loc[
                    :, "{}-{}".format(reg, key)
                ]

            elif "{}-{}".format(reg, key) in lines_list:

                specific_varcost_line = specific_varcost.loc[
                    :, "{}-{}".format(key, reg)
                ]

            variablecost_line_regional[key] = cp.multiply(
                specific_varcost_line, line_import_anunual
            )

        variablecost_line[reg] = variablecost_line_regional

    return variablecost_line

def line_annual_activity(
    line_activity, regions, main_years, time_slices
):

    """
    Calculates the annual line activity
    """

    line_activity_annual = {}

    for reg in regions:

        line_activity_annual_regional = {}

        for key, value in line_activity[reg].items():

            line_activity_annual_regional[key] = annual_activity(value, main_years, time_slices)

        line_activity_annual[reg] = line_activity_annual_regional

    return line_activity_annual


def salvage_factor(
    main_years, technologies, tlft, interest_rate, discount_rate, economiclife
):

    """
    Calculates the salvage factor of the investment cost for the capacities
    that remain after the end of the time horizon to avoid the end of the horizon
    effect
    """

    salvage_factor_0 = pd.DataFrame(0, index=main_years, columns=technologies)

    rates_factor = pd.DataFrame(0, index=main_years, columns=technologies)

    EOH = len(main_years) - 1

    for tech in technologies:

        technical_factor = (1 - 1 / (1 + interest_rate[tech].values)) / (
            1 - 1 / ((1 + interest_rate[tech].values) ** economiclife[tech].values)
        )

        social_factor = (
            1 - 1 / ((1 + discount_rate.values) ** economiclife[tech].values)
        ) / (1 - 1 / (1 + discount_rate.values))

        rates_factor.loc[:, tech] = technical_factor * social_factor

        for indx, year in enumerate(main_years):

            if indx + tlft[tech].values > EOH:

                salvage_factor_0.loc[year, tech] = (
                    (1 + discount_rate.loc[year, :].values)
                    ** (tlft[tech].values - EOH - 1 + indx)
                    - 1
                ) / ((1 + discount_rate.loc[year, :].values) ** tlft[tech].values - 1)

    salvage_factor_mod = pd.DataFrame(
        salvage_factor_0.values * rates_factor.values,
        index=main_years,
        columns=technologies,
    )

    return salvage_factor_mod


def unmet_demand_function(
    unmet_demand, years, timesteps
):

    """
    Calculates cost related to the unmet demand
    """
        
    unmet_demand_bycarrier_annual = []

    for year in range(0, len(years)):

        unmet_demand_bycarrier_annual_rest = cp.sum(
            unmet_demand[(year) * len(timesteps) : (year+1) * len(timesteps)],
            axis=0,
            keepdims=True
        )

        unmet_demand_bycarrier_annual.append(unmet_demand_bycarrier_annual_rest)

    unmet_demand_annual = cp.vstack(unmet_demand_bycarrier_annual)

    return unmet_demand_annual


def storage_state_of_charge(initial_storage, flow_in, flow_out, main_years, time_steps,charge_efficiency,discharge_efficiency, BESS_total_capacity):

    """
    Calculates the state of charge of the storage
    """
    charge_efficiency_reshape = pd.concat(
    [charge_efficiency]
    * len(time_steps)
    ).sort_index()

    discharge_efficiency_reshape = pd.concat(
    [discharge_efficiency]
    * len(time_steps)
    ).sort_index()
    
    BESS_cap = []
    for _ in range(len(main_years)*len(time_steps)):
        BESS_cap.append(cp.multiply(
            BESS_total_capacity[ 0 : 1, :],
            initial_storage.values))
    initial_storage_concat = cp.vstack(BESS_cap)
    
    # initial_storage_concat = pd.concat(
    #     [initial_storage] * len(time_steps) * len(main_years)
    # )
    
    # BESS_capacity = []
    # for indx, year in enumerate(main_years):
    #     BESS_yearly_capacity = []
    #     for _ in enumerate(time_steps):
    #         BESS_yearly_capacity.append(BESS_total_capacity[indx : indx + 1, :])
    #     BESS_yearly_capacity = cp.vstack(BESS_yearly_capacity)
    #     BESS_capacity.append(BESS_yearly_capacity)
    # BESS_capacity_total = cp.vstack(BESS_capacity)
    
    # print(np.shape(BESS_capacity_total))

    state_of_charge = cp.multiply(cp.cumsum(flow_in),charge_efficiency_reshape) + initial_storage_concat  - \
        cp.multiply(cp.cumsum(flow_out),(np.ones((discharge_efficiency_reshape.shape))/discharge_efficiency_reshape.values))

    return state_of_charge


def get_regions_with_storage(sets):

    """
    Finds the regions with storage technologies
    """

    for reg in sets.regions:

        if "Storage" in sets.technologies[reg]:

            yield reg


def storage_max_flow(
    storage_totalcapacity, time, storage_capacity_factor, timeslice_fraction
):
    """
    Calculates the maximum allowed inflow and ouflow of storage technologies
    based on the charge/discharge time and the total nominal capacity
    """

    storage_capacity_available = cp.multiply(
        storage_totalcapacity, storage_capacity_factor
    )

    max_flow = cp.multiply(storage_capacity_available, timeslice_fraction) * 8760 / time # dim = (timesteps, n_storage_tech)

    return max_flow


"""
A helper function used in ReadSets to initialize the column field
of technology-specific parameter files

Parameters
----------
technologies_hierarchy : Dict[str => List[Str]]
    A dictionary defining the mapping between a technology category
    and a list of technologies belonging to that category.
    i.e. {"Supply": ["NG_extraction", "Geo_PP"]}

ignored_tech_categories : List[str]
    A list of technology categories that should be excluded from
    the parameter's file columns

additional_level : None/Touple(str, List[str])
    An additional top hierarchy level to be added to the columns.
    It is in the form (column name, column values).
    i.e. ("Taxes or Subsidies", ["Tax", "Sub"])
"""
def create_technology_columns(
    technologies_hierarchy,
    ignored_tech_categories=["Demand"],
    additional_level=None,
):
    tuples = []
    names = ["Tech_category", "Technology"]
    for tech_category, technologies in technologies_hierarchy.items():
        for technology in technologies:
            tuples.append((tech_category, technology))

    # Remove technologies of ignored categories
    for ignored_tech_category in ignored_tech_categories:
        if ignored_tech_category in technologies_hierarchy.keys():
            tuples = [t for t in tuples if t[0] != ignored_tech_category]

    # Add an additional top level if it was specified
    if additional_level != None:
        additional_level_name = additional_level[0]
        additional_level_values = additional_level[1]

        names.insert(0, additional_level_name)

        new_tuples = []
        for additional_level_value in additional_level_values:
            for t in tuples:
                l = list(t)
                l.insert(0, additional_level_value)
                new_tuples.append(tuple(l))
        tuples = new_tuples

    indexer = pd.MultiIndex.from_tuples(
        tuples, names=names
    )

    return indexer


def get_emission_types(glob_settings):
    return glob_settings["Emissions"]["Emission"].values
