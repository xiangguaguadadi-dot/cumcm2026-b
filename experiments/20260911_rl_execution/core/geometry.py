"""Independent finite fallback geometry; uses only public problem constants."""
from __future__ import annotations
import math

ANGLE_MARGIN_DEG = 1.005001
FALLBACK_VIRTUAL_RESERVE_S = 53000.0
MAX_FALLBACK_BUSINESS_REQUESTS = 5845  # 980 measure + 16*304 clear + EXIT

def discovery_stations():
    xs=(-1800.,-1200.,-600.,0.,600.,1200.,1800.)
    return tuple((x,y) for row,y in enumerate(xs) for x in (xs if row%2==0 else xs[::-1]))

def optical_grid(station, bearing_deg):
    """Column snake: 76 longitudinal points x four transverse levels."""
    a=math.radians(float(bearing_deg)); e=(math.cos(a),math.sin(a)); n=(-e[1],e[0])
    levels=(-30.,-10.,10.,30.)
    return tuple((station[0]+alpha*e[0]+beta*n[0],
                  station[1]+alpha*e[1]+beta*n[1])
                 for j,alpha in enumerate(range(0,1501,20))
                 for beta in (levels if j%2==0 else levels[::-1]))

def polygon_area(poly):
    if len(poly)<3:return 0.
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2.

def fallback_paper_bounds():
    snake=30.+76*60.+75*20.+math.hypot(1500.,30.)
    bound=(5800*math.sqrt(2)+28800)/5+980*6+16*(7591/5+304*3+2)
    return {'discovery_stations':49,'optical_points_per_source':304,
            'max_measure_clear_requests':5844,'max_with_exit':5845,
            'max_transverse_m':1500*math.sin(math.radians(ANGLE_MARGIN_DEG)),
            'optical_snake_with_return_m':snake,'virtual_bound_s':bound,
            'reserved_virtual_s':53000.,'real_time_guarantee':'conditional_only'}
