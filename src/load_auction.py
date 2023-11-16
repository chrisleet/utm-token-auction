class Req():
  def __init__(self, items, utility):
    self.items   = items
    self.utility = utility 

  def __str__(self):
    return f"({self.items}, {self.utility})"

  def __repr__(self):
    return self.__str__()


class Load_WDP:

  def __init__(self, fname):
    with open(fname, "r") as f:
      f.readline()                                  # Skip first line in file
      self.wdp = [self.make_bid(bid_str) for bid_str in f.readlines()]
      
  def make_bid(self, bid_str):
    return [self.make_req(req_str) for req_str in bid_str.strip().split(" XOR ")]

  def make_req(self, req_str):
    # print(f"req_str:{req_str}")
    item_str, utility_str = req_str.split(']')
    items   = [int(token) for token in item_str[1:].split(', ') if token != '']
    utility = int(utility_str)
    return Req(items, utility)


class Load_F:

  def __init__(self, fname):
    with open(fname, "r") as f:
      self.t             = int(f.readline().strip())
      self.all_f_constr  = []

      for line in f:
        tokens    = line.split(",")
        tokens    = [token.split(" ") for token in tokens]
        f_constr  = [(int(bid_id), int(reg_id)) for bid_id, reg_id in tokens]
        self.all_f_constr.append(f_constr)
        # print(f"line:{line} tokens:{tokens} f_constr:{f_constr}")