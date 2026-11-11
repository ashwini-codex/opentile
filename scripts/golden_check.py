import itertools
def run(A,B,R,C,K):
    acc=[[0]*C for _ in range(R)]
    a_reg=[[0]*C for _ in range(R)]; b_reg=[[0]*C for _ in range(R)]
    trace=[]; last_change=-1
    T=K+R+C-2
    for t in range(T+2):
        # feeds this cycle
        a_edge=[A[i][t-i] if 0<=t-i<K else 0 for i in range(R)]
        b_edge=[B[t-j][j] if 0<=t-j<K else 0 for j in range(C)]
        a_in=[[a_edge[i] if j==0 else a_reg[i][j-1] for j in range(C)] for i in range(R)]
        b_in=[[b_edge[j] if i==0 else b_reg[i-1][j] for j in range(C)] for i in range(R)]
        new=[[acc[i][j]+a_in[i][j]*b_in[i][j] for j in range(C)] for i in range(R)]
        if new!=acc: last_change=t
        acc=new; a_reg=a_in; b_reg=b_in
        trace.append([row[:] for row in acc])
    return acc,trace,last_change
import random
for R,C,K in itertools.product(range(1,6),range(1,6),range(1,9)):
    A=[[random.randint(1,5) for _ in range(K)] for _ in range(R)]
    B=[[random.randint(1,5) for _ in range(C)] for _ in range(K)]
    acc,tr,lc=run(A,B,R,C,K)
    ref=[[sum(A[i][k]*B[k][j] for k in range(K)) for j in range(C)] for i in range(R)]
    assert acc==ref
    # final value visible after cycle index K+R+C-3 update, i.e. after K+R+C-2 updates
    assert lc==K+R+C-3,(R,C,K,lc)
print("formula ok")

