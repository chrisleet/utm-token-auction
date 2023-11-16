import cartopy.crs             as ccrs
import cartopy.io.img_tiles    as cimgt
import matplotlib.pyplot       as plt
import networkx                as nx
import shapely.geometry        as sgeom

from cartopy.geodesic          import Geodesic
from collections               import defaultdict, namedtuple
from csv                       import reader
from itertools                 import islice
from matplotlib.transforms     import offset_copy
from pyproj                    import Geod
from random                    import choices, randint
from shapely.geometry          import Point
from shapely.geometry.polygon  import Polygon

Pt = namedtuple('Point', ['x', 'y'])


class Vertex:

  def __init__(self, pt, gps):
    self.pt  = pt
    self.gps = gps


# The region that an airspace hub serves
class Flight_Zone:
  def __init__(self, city, hub, r, parcel_n, company):
    company_map = {"A":1, "B":2, "C":3}

    self.city         = city
    self.hub_gps      = hub
    self.r            = r
    self.parcel_n     = parcel_n
    self.hub_v        = None 
    self.served_v     = None
    self.mission_v    = None
    self.mission_t    = None
    self.missions     = []
    self.company      = company_map[company]


# A mission is a set of flight paths and a price
class Mission:
  def __init__(self, price, m_id):
    self.flight_paths = []
    self.price        = price
    self.m_id         = m_id

# Translates a gps point (x,y) dist distance in the direction az (North is 0)
def translate(geod, pt, az, dist):
  x, y, _ = geod.fwd(lons=pt.x, lats=pt.y, az=az, dist = dist)
  return Pt(x, y)


# Generates a circle to plot on the map
def circle(gd, x, y, r):
  cp = gd.circle(lon=x, lat=y, radius=r)
  return sgeom.Polygon(cp)


# Generates the vertices of a polygon
def polygon(pts):
  return Polygon([(pt.x, pt.y) for pt in pts[::-1]])


# Generates the neighbours of a grid point (x,y)
directions = [(1,0), (-1,0), (0,1), (0,-1)]
def neighbors(pt):
  for dir_x, dir_y in directions:
    yield Pt(pt.x+dir_x, pt.y+dir_y)


# Gets the distance between two gps points
def gps_distance(geod, gps1, gps2):
  return geod.inv(gps1.x, gps1.y, gps2.x, gps2.y)[2]


# Color hub vertices
def hub_cmap(G, zones):
  hub_v = set(z.hub_v for z in zones)
  return ["DeepPink" if v in hub_v else "CornflowerBlue" for v in G.nodes()]


# Color range vertices
def served_color_picker(v, served_v, hub_v):
  if v in served_v:
    return "Thistle"
  elif v == hub_v:
    return "DeepPink"  
  else:
    return "CornflowerBlue"


def served_cmap(G, z):
  served_v = set(z.served_v)
  return [served_color_picker(v, served_v, z.hub_v) for v in G.nodes()]


# Color mission vertices
def mission_color_picker(v, served_v, mission_v, hub_v):
  if v in mission_v:
    return "Brown"
  elif v in served_v:
    return "Thistle"
  elif v == hub_v:
    return "DeepPink"  
  else:
    return "CornflowerBlue"


def mission_cmap(G, z):
  served_v   = set(z.served_v)
  mission_v  = set(z.mission_v)
  return [mission_color_picker(v, served_v, mission_v, z.hub_v) for v in G.nodes()]


# Plot airspace with node_color
def plot_airspace(G, node_color):
    fig         = plt.figure()
    nx.draw(G, nx.get_node_attributes(G, 'pos'), node_size=15, node_color=node_color)
    plt.show()


# Color path vertices
def path_color_picker(v, served_v, path_v, hub_v):
  if v in path_v:
    return "Brown"
  elif v in served_v:
    return "Thistle"
  elif v == hub_v:
    return "DeepPink"  
  else:
    return "CornflowerBlue"


def path_cmap(G, z, p):
  served_v   = set(z.served_v)
  return [path_color_picker(v, served_v, p, z.hub_v) for v in G.nodes()]




def main():

  # Settings
  model_id      = "a"
  cell_meters   = 60  
  mission_hrs   = 1


  # Geodesic map
  geod      = Geod(ellps="WGS84")

  # Center map on Sendai Station
  center    = Pt(140.8824, 38.2601)

  # Get map bounds
  x_meters      = 10e3
  y_meters      = 5e3

  # Get map poles
  east_pole  = translate(geod=geod, pt=center, az=90,  dist=x_meters / 2)
  west_pole  = translate(geod=geod, pt=center, az=270, dist=x_meters / 2)

  north_pole = translate(geod=geod, pt=center, az=0,   dist=y_meters / 2)
  south_pole = translate(geod=geod, pt=center, az=180, dist=y_meters / 2)


  # Get map range
  min_x = west_pole.x
  max_x = east_pole.x

  min_y = south_pole.y
  max_y = north_pole.y

  ### Generate map
  
  # Download tile data from OSM
  request = cimgt.OSM()                                      
  fig     = plt.figure()  

  # Create a GeoAxes with the tile data                                          
  ax = fig.add_subplot(1, 1, 1, projection=request.crs)     

  # Limit the extent of the map to a small longitude/latitude range.
  ax.set_extent([min_x, max_x, min_y, max_y], crs=ccrs.Geodetic())

  # Add the tile data
  ax.add_image(request, 14)

  # Add a marker for sendai station
  # ax.plot(center.x, center.y, marker='o', color='blue', markersize=7, transform=ccrs.Geodetic())


  ### Generate a polygon representing the map bounds
  bounds = polygon([Pt(min_x, min_y), Pt(min_x, max_y), Pt(max_x, max_y), Pt(max_x, min_y)])
  ax.add_geometries([bounds], crs=ccrs.Geodetic(), facecolor='g', edgecolor='k', alpha=0.2)


  ### Generate no-fly zones

  # Load the no fly points
  with open("sendai_data/no_fly.csv", "r") as f:
    nofly_reader = reader(f, delimiter=' ')
    no_fly_polys = defaultdict(list)

    for r in nofly_reader:
      no_fly_polys[r[2]].append(Pt(float(r[0]), float(r[1])))

  # Plot the no fly points
  # for loc, pts in no_fly_polys.items():
  #   for pt in pts:
  #     ax.plot(pt.x, pt.y, marker='x', color='black', markersize=7, transform=ccrs.Geodetic())

  # Plot the no fly zones
  no_fly_geoms = [polygon(pts) for pts in no_fly_polys.values()]
  ax.add_geometries(no_fly_geoms, crs=ccrs.Geodetic(), facecolor='r', edgecolor='k', alpha=0.5)



  ### Generate flight zones

  # Load the flight zones
  with open(f"sendai_data/locs_{model_id}.csv", "r") as f:
    zones_reader = reader(f, delimiter=' ')
    zones = [Flight_Zone(city, Pt(float(x), float(y)), float(r), int(parcel_n), company) 
             for (city, x, y, r, parcel_n, company) in zones_reader
             if bounds.contains(Point(x, y))]

  # Plot the flight zones
  gd = Geodesic()
  zone_geoms = [circle(gd, z.hub_gps.x, z.hub_gps.y, z.r) for z in zones]
  ax.add_geometries(zone_geoms, crs=ccrs.Geodetic(), facecolor='b', edgecolor='k', alpha=0.2)

  for z in zones:
    ax.plot(z.hub_gps.x, z.hub_gps.y, marker='o', color='white',
            markersize=12, transform=ccrs.Geodetic())

  plt.show()


  ### Generate graph                             
  origin      = Pt(min_x, min_y)
  G           = nx.Graph()

  pt_to_v = {}

  grid_x = int(x_meters / cell_meters) + 1
  grid_y = int(y_meters / cell_meters) + 1


  for x in range(0, grid_x):
    for y in range(0, grid_y):

      gps_x = translate(geod=geod, pt=origin, az=90, dist=x * cell_meters)
      gps   = translate(geod=geod, pt=gps_x,   az=0,  dist=y * cell_meters)

      if any(poly.contains(Point(gps.x, gps.y)) for poly in no_fly_geoms):
        continue

      pt = Pt(x,y)
      v  = Vertex(pt, gps)

      pt_to_v[pt] = v
      G.add_node((v), pos=(v.gps.x, v.gps.y))
      # ax.plot(v.gps.x, v.gps.y, marker='x', color='blue', markersize=7, transform=ccrs.Geodetic())

  for pt, v in pt_to_v.items():
    for neighbor_pt in neighbors(pt):
      if neighbor_pt in pt_to_v:
        G.add_edge(v, pt_to_v[neighbor_pt])


  ### Associate zones with vertices
  for z in zones:
    z.hub_v = min(G.nodes, key=lambda v: gps_distance(geod, v.gps, z.hub_gps))
    ax.plot(z.hub_v.gps.x, z.hub_v.gps.y, marker='x', 
            color='orange', markersize=7, transform=ccrs.Geodetic())

  plt.show()

  # node_color=hub_cmap(G, zones)
  # plot_airspace(G, node_color)


  ### Identify vertices in flight range
  for z in zones:
    z.served_v  = [v for v in G.nodes 
                   if gps_distance(geod, v.gps, z.hub_gps) < z.r and v != z.hub_v]

    # print(f"z.r is {z.r}")

    # node_color  = served_cmap(G, z)
    # plot_airspace(G, node_color)


  ### Get missions
  timeslot_min  = 3 
  max_mission_p = 4
  max_price     = 99
  mission_time_slots = list(range(0, 60 * mission_hrs, timeslot_min))

  mission_id          = 0
  bid_cnt             = 0
  all_cells           = set()

  comp_reg_reqs = defaultdict(list)


  for z in zones:
    mission_n   = int(z.parcel_n/10) * mission_hrs
    z.mission_v = choices(z.served_v,         k=mission_n)
    z.mission_t = choices(mission_time_slots, k=mission_n)

    # print(f"Mission_n: {mission_n}")
    # print(f"Mission_v: {[(mission_v.pt.x, mission_v.pt.y) for mission_v in z.mission_v]}")

    # node_color  = mission_cmap(G, z)
    # plot_airspace(G, node_color)


    for mission_v, mission_t in zip(z.mission_v, z.mission_t):

      price       = randint(0, 99)
      path_gen    = nx.all_shortest_paths(G, z.hub_v, mission_v)
      mission     = Mission(price, mission_id)


      for req_id, p in enumerate(islice(path_gen, max_mission_p)):

          cells_fwd  = [int(f"{v.pt.x}0000{v.pt.y}0000{mission_t}")      for v in p]
          cells_back = [int(f"{v.pt.x}0000{v.pt.y}0000{mission_t + 1}")  for v in p[::-1]]
          cells      = cells_fwd + cells_back
          bid_cnt    += 1
          all_cells   |= set(cells)

          for v in p:
            comp_reg_reqs[(z.company, v.pt)].append((mission_id, req_id))

          # print(cells)

          # node_color  = path_cmap(G, z, p)
          # plot_airspace(G, node_color)

          mission.flight_paths.append(cells)

      z.missions.append(mission)
      mission_id += 1

  print(f'Missions:{mission_id} bids_cnt:{bid_cnt} cells in grid:{len(G.nodes)} timeslots:{len(mission_time_slots)}')
  print(f'total cells:{len(G.nodes)* len(mission_time_slots)} cells_bid_on:{len(all_cells)} hours:{mission_hrs} cell meters:{cell_meters}')

  with open(f"scen/model{model_id}-wdp-hrs{mission_hrs}-cell_meters{cell_meters}.wdp", "w") as f:
    print(f"{sum(len(z.missions) for z in zones)}", file=f)

    for z in zones:
      for m in z.missions:
        mission_strs = [f"{path} {m.price}" for path in m.flight_paths]
        print(" XOR ".join(mission_strs), file=f)

  with open(f"scen/model{model_id}-wdp-hrs{mission_hrs}-cell_meters{cell_meters}-f.wdp", "w") as g:
    print(f"{len(mission_time_slots)}", file=g)

    for reqs in comp_reg_reqs.values():
      print(",".join([f"{m_id} {req_id}" for (m_id, req_id) in reqs]), file=g)

if __name__ == '__main__':
  main()