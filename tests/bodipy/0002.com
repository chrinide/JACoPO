%nprocshared=12
%mem=2500MW
%chk=0002.chk
#p td=(nstates=1) cam-b3lyp cc-pVTZ nosymm density(transition=1) IOp(9/40=5) 

bodipy_monomer_camccpvtz

0 1
 C                  0.33748610   -1.44761768   -0.65293808
 C                 -0.01309972   -0.62922380   -1.75700922
 C                  1.41587936   -2.22383670   -1.04881524
 N                  0.85710919   -0.92101213   -2.80513566
 C                 -1.00993822    0.32651034   -1.90987709
 H                  1.94537881   -2.96149584   -0.46671979
 C                  1.70469983   -1.86777289   -2.38305916
 B                  0.83438895   -0.24976865   -4.22305789
 H                 -1.67310193    0.53372266   -1.07812794
 C                 -1.18021809    1.02397774   -3.09942630
 H                  2.47399070   -2.25092205   -3.03696658
 N                 -0.34602770    0.78320897   -4.18898118
 F                  2.03808019    0.40980547   -4.45729299
 F                  0.59777689   -1.21151662   -5.20174696
 C                 -2.11375569    2.02452089   -3.47235122
 C                 -0.73377992    1.58628849   -5.18779343
 C                 -1.83111519    2.37547091   -4.78350153
 H                 -2.89014384    2.42201826   -2.83596109
 H                 -0.22313683    1.56950912   -6.13919699
 H                 -2.33821107    3.10612983   -5.39369585
 H                 -0.15382019   -1.44761768    0.29759762

