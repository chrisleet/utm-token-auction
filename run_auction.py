import gurobipy             as     gp

from   collections          import defaultdict
from   gurobipy             import GRB

from   time                 import time

from src.load_auction import Load_F, Load_WDP

class WDP():

  def __init__(self):
    
    # (1) Load WDP
    model   = "a"
    hrs     = "2"
    meters  = "150"
    is_fair = True
    fairness_const = 0.2


    load_wdp = Load_WDP(f"scen/model{model}-wdp-hrs{hrs}-cell_meters{meters}.wdp")
    wdp      = load_wdp.wdp
    # print(wdp)

    # (2) Load F
    load_f   =  Load_F(f"scen/model{model}-wdp-hrs{hrs}-cell_meters{meters}-f.wdp")

    t= time()

    # (2) Get the items requested for each bid
    bid_id_to_items = {bid_id:self.get_req_items(bid) for bid_id, bid in enumerate(wdp)}
    all_items       = set().union(*bid_id_to_items.values())



    # (3) Initialize ILP model
    model = gp.Model("wdp_ILP")

    # (4) Ensure that each item is assigned to at most one bid
    var = {}

    for bid_id, items in bid_id_to_items.items():
      for item in items: 
        var_name      = self.assign_var(item, bid_id)
        var[var_name] = model.addVar(vtype=GRB.BINARY, name=var_name)

    for item in all_items:
      bid_ids        = [bid_id for bid_id, items in bid_id_to_items.items() if item in items]
      assignment_sum = gp.quicksum(var[self.assign_var(item, bid_id)] for bid_id in bid_ids)
      constr_name    = self.item_constr(item)

      model.addConstr(assignment_sum <= 1, name=constr_name) 

    # (5) Req satisfiability constraints:
    for bid_id, bid in enumerate(wdp):

      # (a) A bid's req can only be satisfied if all of its items are assigned to the bid
      for req_id, req in enumerate(bid):

        var_name       = self.sat_var(bid_id, req_id)
        var[var_name]  = model.addVar(vtype=GRB.BINARY, name=var_name)

        items          = [var[self.assign_var(item, bid_id)] for item in req.items]
        constr_name    = self.req_constr(bid_id, req_id)

        model.addConstr(len(items) * var[var_name] <= gp.quicksum(items), name=constr_name)


      # (b) At most one of a bid's reqs can be satisfied
      req_sum     = gp.quicksum([var[self.sat_var(bid_id, req_id)] for req_id in range(len(bid))])
      constr_name = self.bid_constr(bid_id)

      model.addConstr(req_sum <= 1, name=constr_name)


    # (7) Fairness constraints
    if is_fair:
      req_density = int(load_f.t * fairness_const)

      for f_id, f_constr in enumerate(load_f.all_f_constr):

        reqs        = [var[self.sat_var(bid_id, req_id)] for (bid_id, req_id) in f_constr]

        constr_name = self.fair_constr(f_id)

        model.addConstr(gp.quicksum(reqs) <= req_density, name=constr_name)
        # model.update()

        # for constr in model.getConstrs():
        #   if constr.ConstrName == constr_name:
        #     print(f"f_constr:{f_constr}, req_density:{req_density}")
        #     print(f"{constr.ConstrName}:  {self.constr_to_eq(constr, model)}")
        #     input("")




    # (7) The goal is to maximize the value of the satisfied reqs
    req_utility = gp.quicksum(req.utility*var[self.sat_var(bid_id, req_id)] 
                              for bid_id, bid in enumerate(wdp)
                              for req_id, req in enumerate(bid))

    model.setObjective(req_utility, GRB.MAXIMIZE)


    # (8) Print model
    model.optimize()

    print(f"model.status: {model.status}")

    print(f"Runtime:{time()-t}")

    # for constr in model.getConstrs():
    #   print(f"{constr.ConstrName}:  {self.constr_to_eq(constr, model)}")

    # for v in model.getVars():
    #   print(f"{v.varName}: val:{v.x:.2f}")

    # if model.status == 2:
    #   for bid_id, bid in enumerate(wdp):
    #     for req_id, req  in enumerate(bid):
    #       if var[self.sat_var(bid_id, req_id)].x == 1:
    #         print(req)



  def get_req_items(self, bid):
    return set().union(*[req.items for req in bid])

  def assign_var(self, item, bid_id):
    return f"assign-b({bid_id})-i({item})"

  def sat_var(self, bid_id, req_id):
    return f"sat-b({bid_id})-r({req_id})"

  def item_constr(self, item):
    return f"i-constr-i({item})"

  def req_constr(self, bid_id, req_id):
    return f"r-constr-b({bid_id})-r({req_id})"

  def bid_constr(self, bid_id):
    return f"b-constr-b({bid_id})"

  def fair_constr(self, fair_id):
    return f"f-constr-({fair_id})"

  def constr_to_eq(self, constr, model):
    lhs_str = ""
    row     = model.getRow(constr)

    for k in range(row.size()):
      name  = row.getVar(k).VarName
      coeff = row.getCoeff(k)

      if   coeff == 1:
        lhs_str += f" + {name}"
      elif coeff >= 0:
        lhs_str += f" + {coeff:.2f}*{name}"
      elif coeff == -1:
        lhs_str += f" - {name}"
      else:
        lhs_str += f" - {coeff:.2f}*{name}"

    match constr.sense:
      case gp.GRB.LESS_EQUAL:
        sense_str = "<="
      case gp.GRB.EQUAL:
        sense_str = "=="
      case gp.GRB.GREATER_EQUAL:
        sense_str = ">="

    return f"{lhs_str[1:]} {sense_str} {constr.RHS:.2f}"





if __name__ == "__main__":
  WDP()