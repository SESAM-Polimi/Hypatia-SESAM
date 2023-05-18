# -*- coding: utf-8 -*-
"""
This module contains the core of the optimization model, containing
the definiton of problem (variables,constraints,objective function,...)
in CVXPY for planning and operation modes.
"""
import pandas as pd
import cvxpy as cp
import numpy as np
from collections import namedtuple
from hypatia.backend.ModelData import ModelData
from hypatia.backend.ModelVariables import ModelVariables
from hypatia.utility.constants import ModelMode, OptimizationMode, EnsureFeasibility
from hypatia.utility.utility import (
    _calc_variable_overall,
    _calc_production_overall,
    available_resource_prod,
    annual_activity,
    get_regions_with_storage,
    storage_max_flow,
    get_emission_types,
)
from hypatia.backend.constraints.ConstraintList import CONSTRAINTS
import logging
from plotly import graph_objs as go


logger = logging.getLogger(__name__)


RESULTS = [
    "technology_prod",
    "production_annual",
    "technology_use",
    "consumption_annual",
    "line_import",
    "line_import_annual",
    "line_export",
    "line_export_annual",
    "unmet_demand_annual",
    "cost_fix",
    "cost_variable",
    "totalcapacity",
    "cost_fix_tax",
    "cost_fix_sub",
    "cost_unmet_demand",
    "emission_cost_by_type",
    "emission_cost_by_region",
    "emission_by_type",
    "captured_emission_by_type",
    "used_emissions_by_type",
    "demand",
    "storage_SOC",
    "residual_capacity",
    "carrier_ratio_in",
    "carrier_ratio_out",
    "tot_emissions",
    "unmetdemandbycarrier"
]

PLANNING_RESULTS = [
    "cost_decom",
    "decommissioned_capacity",
    "new_capacity",
    "real_new_capacity",
    "cost_inv",
    "salvage_inv",
    "cost_inv_tax",
    "cost_inv_sub",
]


class BuildModel:

    """Class that builds the variables and equations of the model

    Attributes
    -----------
    sets:
        The instance of the Readsets class for delivering the structural inputs
        including regions, technologies, years, timesteps, mapping tables

    variables: dict
        a nested dictionary of all the decision variables including the new capacity, production
        by each technology, use (consumption) by each technology, imports and exports

    """

    def __init__(self, model_data: ModelData):

        self.model_data = model_data

        # define all primary and secondary variables
        self.vars = ModelVariables(self.model_data)

        # create all constraints
        self.constr = []
        for constraint in CONSTRAINTS:
            self.constr += constraint(self.model_data, self.vars).get()
            
        
        timeslice_fraction = self.model_data.settings.timeslice_fraction
        if not isinstance(timeslice_fraction, int):
            timeslice_fraction.shape = (len(self.model_data.settings.time_steps), 1)
        self.timeslice_fraction = timeslice_fraction

        # calling the methods based on the defined mode by the user
        if self.model_data.settings.optimization == OptimizationMode.Multi:
            self._set_regional_emission_objective()
            self._set_final_emission_objective()
            
        if self.model_data.settings.mode == ModelMode.Planning:
            self._set_regional_objective_planning()

            if not self.model_data.settings.multi_node:
                self._set_final_objective_singlenode()
            else:
                self._set_lines_objective_planning()
                self._set_final_objective_multinode()

        elif self.model_data.settings.mode == ModelMode.Operation:
            self._set_regional_objective_operation()

            if not self.model_data.settings.multi_node:
                self._set_final_objective_singlenode()
            else:
                self._set_lines_objective_operation()
                self._set_final_objective_multinode()
                
        self.NPC = self.global_objective
        if self.model_data.settings.optimization == OptimizationMode.Multi:
            self.total_emission = self.global_emission_objective
                    

    def _solve(self, verbosity, solver, **kwargs):

        """
        Creates a CVXPY problem instance, if the output status is optimal,
        returns the results to the interface
        """

        objective = cp.Minimize(self.global_objective)
        problem = cp.Problem(objective, self.constr)
        problem.solve(solver=solver, verbose=verbosity, **kwargs)

        if problem.status == "optimal":

            res = RESULTS.copy()
            to_add = []
            if self.model_data.settings.multi_node:
                if self.model_data.settings.mode == ModelMode.Planning:
                    to_add = [
                        "line_totalcapacity",
                        "line_new_capacity",
                        "real_new_line_capacity",
                        "line_decommissioned_capacity",
                        "cost_inv_line",
                        "cost_fix_line",
                        "cost_decom_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
                else:
                    to_add = [
                        "line_totalcapacity",
                        "cost_fix_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
            else:
                to_add = [
                    "tot_cost_single_node"
                    ]

                
            if self.model_data.settings.mode == ModelMode.Planning:
                to_add.extend(PLANNING_RESULTS)

            res.extend(to_add)
            result_collector = namedtuple("result", res)
            results = result_collector(
                **{result: getattr(self.vars, result) for result in res}
            )

            return results

        else:
            print(
                "No solution found and no result will be uploaded to the model",
                "critical",
            )
            
    def _solve_MO(self, number_solutions, path, verbosity, solver, **kwargs):

        """
        Creates a CVXPY problem instance, if the output status is optimal,
        returns the results to the interface
        """ 
        
        if self.model_data.settings.optimization == OptimizationMode.Single:
            return print(
                    "Wrong run function. Use run"
                    ) 
            
        objective = cp.Minimize(self.global_objective)     
        problem = cp.Problem(objective, self.constr)
        problem.solve(solver=solver, verbose=verbosity, **kwargs)

        if problem.status == "optimal":

            res = RESULTS.copy()
            to_add = []
            if self.model_data.settings.multi_node:
                if self.model_data.settings.mode == ModelMode.Planning:
                    to_add = [
                        "line_totalcapacity",
                        "line_new_capacity",
                        "real_new_line_capacity",
                        "line_decommissioned_capacity",
                        "cost_inv_line",
                        "cost_fix_line",
                        "cost_decom_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
                else:
                    to_add = [
                        "line_totalcapacity",
                        "cost_fix_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
            else:
                to_add = [
                    "tot_cost_single_node"
                    ]
                
            if self.model_data.settings.mode == ModelMode.Planning:
                to_add.extend(PLANNING_RESULTS)

            res.extend(to_add)
            result_collector = namedtuple("result", res)
            results = result_collector(
                **{result: getattr(self.vars, result) for result in res}
            )
            
            Min_NPC = self.global_objective.value
            Max_emissions = results.tot_emissions.value

        else:
            print(
                "No solution found and no result will be uploaded to the model",
                "critical",
            )
            
        objective = cp.Minimize(self.global_emission_objective)     
        problem = cp.Problem(objective, self.constr)
        problem.solve(solver=solver, verbose=verbosity, **kwargs)

        if problem.status == "optimal":

            res = RESULTS.copy()
            to_add = []
            if self.model_data.settings.multi_node:
                if self.model_data.settings.mode == ModelMode.Planning:
                    to_add = [
                        "line_totalcapacity",
                        "line_new_capacity",
                        "real_new_line_capacity",
                        "line_decommissioned_capacity",
                        "cost_inv_line",
                        "cost_fix_line",
                        "cost_decom_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
                else:
                    to_add = [
                        "line_totalcapacity",
                        "cost_fix_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
            else:
                to_add = [
                    "tot_cost_single_node"
                    ]
                
            if self.model_data.settings.mode == ModelMode.Planning:
                to_add.extend(PLANNING_RESULTS)

            res.extend(to_add)
            result_collector = namedtuple("result", res)
            results = result_collector(
                **{result: getattr(self.vars, result) for result in res}
            )
            
            if self.model_data.settings.multi_node:
                Max_NPC = results.tot_cost_multi_node.value
            else:
                Max_NPC = results.tot_cost_single_node.value
            Min_emissions = self.global_emission_objective.value  
            
        else:
            print(
                "No solution found and no result will be uploaded to the model",
                "critical",
            )
        
        step = (Max_emissions-Min_emissions)/(number_solutions-1)
             
        i = 1        
        emission_list = []
        while i < (number_solutions-1):
            emission_list.append(Max_emissions-i*step)
            i += 1
        
        NPC_list = []
        for emis in emission_list:
            new_constr = [self.vars.tot_emissions <= emis]
            objective = cp.Minimize(self.global_objective)     
            problem = cp.Problem(objective, self.constr + new_constr)
            problem.solve(solver=solver, verbose=verbosity, **kwargs)

            if problem.status == "optimal":

                res = RESULTS.copy()
                to_add = []
                if self.model_data.settings.multi_node:
                    if self.model_data.settings.mode == ModelMode.Planning:
                        to_add = [
                            "line_totalcapacity",
                            "line_new_capacity",
                            "real_new_line_capacity",
                            "line_decommissioned_capacity",
                            "cost_inv_line",
                            "cost_fix_line",
                            "cost_decom_line",
                            "cost_variable_line",
                            "tot_cost_multi_node"
                        ]
                    else:
                        to_add = [
                            "line_totalcapacity",
                            "cost_fix_line",
                            "cost_variable_line",
                            "tot_cost_multi_node"
                        ]
                else:
                    to_add = [
                        "tot_cost_single_node"
                        ]
                    
                if self.model_data.settings.mode == ModelMode.Planning:
                    to_add.extend(PLANNING_RESULTS)

                res.extend(to_add)
                result_collector = namedtuple("result", res)
                results = result_collector(
                    **{result: getattr(self.vars, result) for result in res}
                )
                
                NPC_list.append(self.global_objective.value)
                
                new_constr = []
                
            else:
                print(
                    "No solution found and no result will be uploaded to the model",
                    "critical",
                )
                
        emission_list = [Max_emissions] + emission_list + [Min_emissions]
        NPC_list = [Min_NPC] + NPC_list + [Max_NPC]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=emission_list,
            y=NPC_list,
            mode='lines+markers',
            marker=dict(
                size=10,
                color='red',
                symbol='circle'
            )
        ))

        fig.update_layout(
            title='Pareto Frontier',
            xaxis_title='emissions [kg]',
            yaxis_title='NPC [$]'
        )
        
        fig.write_html(path)
        
        emission_ = emission_list[0:number_solutions-1]
        NPC_ = NPC_list[0:number_solutions-1]
            
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=emission_,
            y=NPC_,
            mode='lines+markers',
            marker=dict(
                size=10,
                color='red',
                symbol='circle'
            )
        ))

        fig.update_layout(
            title='Pareto Frontier without max NPC',
            xaxis_title='emissions [kg]',
            yaxis_title='NPC [$]'
        )
        
        fig.write_html(path)
        
        print("Emissions = " +str(emission_list))
        print("NPCs = " +str(NPC_list))
        
        solution = int(input("Please select one of the solution entering a number between 1 and Number_solutions (1: Min NPC, Number_solutions: Min Emissions): "))
        
        selected_emission_value = emission_list[solution-1]
        print("Selected emission value = " + str(selected_emission_value))
        self.constr += [self.vars.tot_emissions <= emission_list[solution-1]]
        objective = cp.Minimize(self.global_objective)     
        problem = cp.Problem(objective, self.constr)
        problem.solve(solver=solver, verbose=verbosity, **kwargs)

        if problem.status == "optimal":

            res = RESULTS.copy()
            to_add = []
            if self.model_data.settings.multi_node:
                if self.model_data.settings.mode == ModelMode.Planning:
                    to_add = [
                        "line_totalcapacity",
                        "line_new_capacity",
                        "real_new_line_capacity",
                        "line_decommissioned_capacity",
                        "cost_inv_line",
                        "cost_fix_line",
                        "cost_decom_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
                else:
                    to_add = [
                        "line_totalcapacity",
                        "cost_fix_line",
                        "cost_variable_line",
                        "tot_cost_multi_node"
                    ]
            else:
                to_add = [
                    "tot_cost_single_node"
                    ]
                
            if self.model_data.settings.mode == ModelMode.Planning:
                to_add.extend(PLANNING_RESULTS)

            res.extend(to_add)
            result_collector = namedtuple("result", res)
            results = result_collector(
                **{result: getattr(self.vars, result) for result in res}
            )
            
        else:
            print(
                "No solution found and no result will be uploaded to the model",
                "critical",
            )
                
        return results

    def _set_regional_objective_planning(self):

        """
        Calculates the regional objective function in the planning mode
        """

        self.totalcost_allregions = np.zeros((len(self.model_data.settings.years), 1))
        self.inv_allregions = 0
        years = -1 * np.arange(len(self.model_data.settings.years))

        for reg in self.model_data.settings.regions:

            totalcost_regional = np.zeros((len(self.model_data.settings.years), 1))

            for ctgry in self.model_data.settings.technologies[reg].keys():

                if ctgry != "Demand":

                    totalcost_regional += cp.sum(
                        self.vars.cost_inv_tax[reg][ctgry]
                        - self.vars.cost_inv_sub[reg][ctgry]
                        + self.vars.cost_fix[reg][ctgry]
                        + self.vars.cost_fix_tax[reg][ctgry]
                        - self.vars.cost_fix_sub[reg][ctgry]
                        + self.vars.cost_variable[reg][ctgry]
                        + self.vars.cost_decom[reg][ctgry]
                        - self.vars.salvage_inv[reg][ctgry],
                        axis=1,
                    )

                    self.inv_allregions += self.vars.cost_inv_fvalue[reg][ctgry]

                    if ctgry != "Transmission" and ctgry != "Storage":
                        for emission_type in get_emission_types(self.model_data.settings.global_settings):
                            totalcost_regional += cp.sum(
                                self.vars.emission_cost_by_region[reg][emission_type][ctgry], axis=1
                            )
            for carr in self.vars.unmetdemandbycarrier[reg].keys():
                            
                totalcost_regional += cp.sum(self.vars.cost_unmet_demand[reg][carr],axis=1)                

            discount_factor = (
                1 + self.model_data.regional_parameters[reg]["discount_rate"]["Annual Discount Rate"].values
            )

            totalcost_regional_discounted = cp.multiply(
                totalcost_regional, np.power(discount_factor, years)
            )
            self.totalcost_allregions += totalcost_regional_discounted
            
    def _set_regional_emission_objective(self):
        """
        Calculates the regional emission objective function in the planning mode
        """
        self.totalemission_allregions = np.zeros((len(self.model_data.settings.years), 1))
        
        for reg in self.model_data.settings.regions:
            
            totalemission_regional = np.zeros((len(self.model_data.settings.years), 1))
            
            for emission_type in get_emission_types(self.model_data.settings.global_settings):
                
                totalemission_regional_by_type = np.zeros((len(self.model_data.settings.years), 1))
                
                for ctgry in self.model_data.settings.technologies[reg].keys():

                    if ctgry != "Demand" and ctgry != "Transmission" and ctgry != "Storage":
                        
                        totalemission_regional_by_type += cp.sum(
                            self.vars.emission_by_region[reg][emission_type][ctgry], axis=1
                        )
                        
                totalemission_regional += totalemission_regional_by_type
                
            self.totalemission_allregions += totalemission_regional

    def _set_regional_objective_operation(self):

        """
        Calculates the regional objective function in the operation mode
        """
        self.totalcost_allregions = 0
        for reg in self.model_data.settings.regions:

            totalcost_regional = 0

            for ctgry in self.model_data.settings.technologies[reg].keys():

                if ctgry != "Demand":

                    totalcost_regional += cp.sum(
                        self.vars.cost_fix[reg][ctgry]
                        + self.vars.cost_fix_tax[reg][ctgry]
                        - self.vars.cost_fix_sub[reg][ctgry]
                        + self.vars.cost_variable[reg][ctgry]
                    )

                    if ctgry != "Transmission" and ctgry != "Storage":
                        for emission_type in get_emission_types(self.model_data.settings.global_settings):
                            totalcost_regional += cp.sum(
                                self.vars.emission_cost_by_region[reg][emission_type][ctgry], axis=1
                            )
                            
            for carr in self.vars.unmetdemandbycarrier[reg].keys():
                            
                totalcost_regional += cp.sum(self.vars.cost_unmet_demand[reg][carr],axis=1) 

            self.totalcost_allregions += totalcost_regional

    def _set_lines_objective_planning(self):

        """
        Calculates the objective function of the inter-regional links in the
        planning mode
        """

        years = -1 * np.arange(len(self.model_data.settings.years))
        self.totalcost_lines = np.zeros((len(self.model_data.settings.years), 1))

        for line in self.model_data.settings.lines_list:

            self.totalcost_lines += cp.sum(
                self.vars.cost_inv_line[line]
                + self.vars.cost_fix_line[line]
                + self.vars.cost_decom_line[line],
                axis=1,
            )

        for reg in self.model_data.settings.regions:

            for key, value in self.vars.cost_variable_line[reg].items():

                self.totalcost_lines += cp.sum(value, axis=1)

        discount_factor_global = (
            1
            + self.model_data.global_parameters["global_discount_rate"][
                "Annual Discount Rate"
            ].values
        )

        self.totalcost_lines_discounted = cp.multiply(
            self.totalcost_lines, np.power(discount_factor_global, years)
        )

    def _set_lines_objective_operation(self):

        """
        Calculates the objective function of the inter-regional links in the
        operation mode
        """

        self.totalcost_lines = np.zeros((len(self.model_data.settings.years), 1))

        for line in self.model_data.settings.lines_list:

            self.totalcost_lines += cp.sum(self.vars.cost_fix_line[line], axis=1)

        for reg in self.model_data.settings.regions:

            for key, value in self.vars.cost_variable_line[reg].items():

                self.totalcost_lines += cp.sum(value, axis=1)

    def _set_final_objective_singlenode(self):

        """
        Calculates the overall objective function in a single-node model
        """
        if self.model_data.settings.mode == ModelMode.Planning:
            self.global_objective = (
                cp.sum(self.totalcost_allregions) + self.inv_allregions
            )

        elif self.model_data.settings.mode == ModelMode.Operation:

            self.global_objective = self.totalcost_allregions

    def _set_final_objective_multinode(self):

        """
        Calculates the overall objective function as the summation of all the
        regional and inter-regional links objective functions in a multi-node
        model
        """

        if self.model_data.settings.mode == ModelMode.Planning:

            self.global_objective = (
                cp.sum(self.totalcost_lines_discounted + self.totalcost_allregions)
                + self.inv_allregions
            )

        elif self.model_data.settings.mode == ModelMode.Operation:

            self.global_objective = self.totalcost_allregions + self.totalcost_lines
            
    def _set_final_emission_objective(self):

        """
        Calculates the overall emission objective function 
        """
        if self.model_data.settings.mode == ModelMode.Planning:
            self.global_emission_objective = cp.sum(self.totalemission_allregions)

        elif self.model_data.settings.mode == ModelMode.Operation:

            self.global_emission_objective = self.totalemission_allregions
