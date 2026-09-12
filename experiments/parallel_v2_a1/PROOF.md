# Completeness and ordering objective

Let P be the inherited convex polygon of possible source locations. Only actual bounded-error bearings, no-signal constraints appropriate to the mode, and failed clear observations update P. The new planner does not change P.

A sequence of parallel supporting half-plane cuts partitions P into convex cells C1,...,Ck whose union is P. Each cell must have a computed enclosing radius below 20 - 1e-5 metres. A proposed clear position qj is shifted within that cell's conservative service disk, then every cell vertex is explicitly checked to be within 20 - 1e-6 metres of qj. Because a Euclidean norm is convex, this vertex check proves that the entire convex cell lies inside the clear disk centred at qj. Hence P is covered by the complete family of clear disks.

All disks remain in the returned sequence. If an early clear succeeds, the source is removed. If the first k-1 attempts fail, the source lies outside those k-1 disks but still lies in P; it therefore must lie inside the last disk. The last clear is consequently certified. This argument does not depend on the finite planning sample or its probability assumptions, and optical success does not depend on transmitter direction. Each plan has at most six clear calls in R6/R7. Each call retains the inherited interface acceptance and real-time guards. R5 and later also restore the inherited virtual-time fallback before planning.

For a **fixed collection of clear positions and a fixed discrete planning distribution**, let M be the subset already attempted and let s(M) be the probability mass not yet covered. A transition from previous position i to clear point j contributes

    s(M) * (distance(i,j)/5 + 3)

to expected travel/optical-inspection cost. Since a successful clear adds two seconds exactly once, and the full collection covers every planning hypothesis, add a constant two seconds at the end. The subset DP state (M,i) suffices: after each unsuccessful clear the only continuing observation is failure, while success terminates this source's sequence. All complete orders are represented, so the DP minimizes this discrete fixed-point objective. Thirty small instances were checked independently against all permutations, with a largest numerical difference of 4.2633e-14 seconds.

This is **not** a proof of globally optimal search for the contest problem. The uniform-area quadrature, the radio-continuation cost, the disk collection, the strip directions, and the source scheduling all remain modeling/algorithm choices. Local expected-cost improvements need not improve every case or the final closed-loop mean, so every retained candidate is executed on the full frozen regression cases.
