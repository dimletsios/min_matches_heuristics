from __future__ import division
from pyomo.environ import *
from pyomo.opt import SolverFactory
from ..problem_classes.heat_exchange import *
from solver_statistics import Solver_Statistics
from ..io_modules.readers import read_nodes_explored


def solve_transportation_mip(test_set,test_id,solver,timeout,inst):

	model = AbstractModel()
	
	model.n = Param(within=NonNegativeIntegers, initialize=inst.n) # number of hot streams
	model.m = Param(within=NonNegativeIntegers, initialize=inst.m) # number of cold streams
	model.k = Param(within=NonNegativeIntegers, initialize=inst.k) # number of temperature intervals
	
	model.H = RangeSet(0, model.n-1) # set of hot streams
	model.C = RangeSet(0, model.m-1) # set of cold streams
	model.TI = RangeSet(0, model.k-1) # set of temperature intervals

	# Parameter: heat load of hot stream i in temperature interval t 
	model.QH = Param(model.H, model.TI, within=NonNegativeReals, initialize=lambda model, i, t: inst.QH[i][t])

	# Paramter: heat load of cold stream j in temperature interval t
	model.QC = Param(model.C, model.TI, within=NonNegativeReals, initialize=lambda model, j, t: inst.QC[j][t])
	
	# Parameter: upper bound on the heat exchanged between hot stream i and cold stream j
	model.U = Param(model.H, model.C, within=NonNegativeReals, initialize=lambda model, i, j: inst.U[i][j])
	
	model.forbidden_quadruples = Set(within=model.H*model.TI*model.C*model.TI, initialize=inst.forbidden_quadruples)  
	
	# Variable: number of matches
	model.matches = Var(within=NonNegativeIntegers)
    
	# Variable: binary specifying whether hot stream i is matched to cold stream j
	model.y = Var(model.H, model.C, within=Binary)
    
	# Variable: heat transferred to cold stream j within temperature interval t from hot stream i
	model.q = Var(model.H, model.TI, model.C, model.TI, within=NonNegativeReals)
    
	# Objective: minimization of the number of matches
	def number_matches_rule(model):
		return model.matches
	model.obj_value = Objective(rule=number_matches_rule, sense=minimize)
	
	# Constraint: matches enumeration
	def matches_sum_rule(model):
		return model.matches == sum(model.y[i,j] for i in model.H for j in model.C)
	model.matches_sum_constraint = Constraint(rule=matches_sum_rule)   
    
	#Constraint: heat conservation of hot streams
	def hot_conservation_rule(model, i, ti):
		return sum(model.q[i,ti,j,tj] for j in model.C for tj in model.TI) == model.QH[i,ti]
	model.hot_conservation_constraint = Constraint(model.H, model.TI, rule=hot_conservation_rule)
    
	#Constraint: heat conservation of cold streams
	def cold_conservation_rule(model, j, tj):
		return sum(model.q[i,ti,j,tj] for i in model.H for ti in model.TI) == model.QC[j,tj]
	model.cold_conservation_constraint = Constraint(model.C, model.TI, rule=cold_conservation_rule)
    
	# Constraint: matched streams
	def matched_streams_rule(model, i, j):
		return sum(model.q[i,ti,j,tj] for ti in model.TI for tj in model.TI) <= model.U[i,j]*model.y[i,j]
	model.matched_streams_constraint = Constraint(model.H, model.C, rule=matched_streams_rule)    

	#Constraint: not allowed transfers
	def forbidden_combinations_rule(model, i, ti, j, tj):
		return model.q[i,ti,j,tj] == 0
	model.forbidden_combinations_constraint = Constraint(model.forbidden_quadruples, rule=forbidden_combinations_rule)  

	opt = SolverFactory(solver)
	opt.options['threads'] = 1
	opt.options['logfile'] = 'data/mip_solutions/'+test_set+'/transportation/'+test_id+'_'+solver+'.log'
	opt.options['mipgap'] = 0.04
	opt.options['timelimit'] = timeout
	mip_instance = model.create_instance()
	results = opt.solve(mip_instance)
	
	elapsed_time = results.solver.time
	nodes_explored = read_nodes_explored(test_set,test_id,solver,'transportation')
	lower_bound = results.problem.lower_bound
	upper_bound = results.problem.upper_bound
	
	stats = Solver_Statistics(elapsed_time, nodes_explored, lower_bound, upper_bound)
	
	matches=mip_instance.matches.value
	y=[[mip_instance.y[i,j].value for j in range(inst.m)] for i in range(inst.n)]
	q=[[[[mip_instance.q[i,ti,j,tj].value for tj in range(inst.k)] for j in range(inst.m)] for ti in range(inst.k)] for i in range(inst.n)]
	
	sol=Heat_Exchange('transportation',inst.n,inst.m,inst.k,matches,y,q)
	return (sol, stats)
	
	
	
	