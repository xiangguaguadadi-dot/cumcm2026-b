"""Question 2 conservative candidate region for an omnidirectional source."""
import math

def safe_local(x,y,delta_deg=1.005001):
    delta=math.radians(delta_deg);r2=x*x+y*y
    return r2<=1_000_000 and r2<=2000*(x*math.cos(delta)-abs(y)*math.sin(delta))

def second_points(first,bearing_deg):
    a=math.radians(bearing_deg);c,s=math.cos(a),math.sin(a)
    return [(first[0]+600*c-y*s,first[1]+600*s+y*c) for y in (300,-300)]

if __name__=='__main__':
    for x,y in [(600,300),(600,-300),(0,300)]:print((x,y),safe_local(x,y))
    print(second_points((0,0),0))
