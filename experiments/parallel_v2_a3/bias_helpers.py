def _a3_inside(poly,q):
    signs=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        z=(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])
        if abs(z)>1e-6:signs.append(z>0)
    return not signs or all(s==signs[0] for s in signs)
