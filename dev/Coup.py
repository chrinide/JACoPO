#!/usr/bin/env python

import sys
import time
import numpy as np
import argparse as arg
from elements import ELEMENTS

try:
    import trden
    FModule = True

except ImportError:
    print(" WARNING!!!")
    print(" The Fortran Module could not be loaded.")
    print(" Coupling from Transition Densities will not be computed.")
    FModule = False

# Constants

au2ang = 0.5291771
au2wn = 2.194746e5

def options():
    '''Defines the options of the script.'''

    parser = arg.ArgumentParser(description='Calculates Electronic Coupling from Transition Charges and Densities.', formatter_class=arg.ArgumentDefaultsHelpFormatter)

    # Optional arguments
    parser.add_argument('--chg1', default='mon1.chg', type=str, help='''File with coordinates and charges for monomer 1.''')

    parser.add_argument('--chg2', default='mon2.chg', type=str, help='''File with coordinates and charges for monomer 2.''')

    parser.add_argument('--cub1', default='mon1.cub', type=str, help='''Transition Density Cube for monomer 1.''')

    parser.add_argument('--cub2', default='mon2.cub', type=str, help='''Transition Density Cube for monomer 2.''')

    parser.add_argument('--thresh', default=1e-5, type=float, help='''Threshold for Transition Density Cubes.''')

    parser.add_argument('--coup', default=None, type=str, choices=['chgs', 'den'], help='''Method of Calculation of the Electronic Coupling.''')

    parser.add_argument('-o', '--output', default='Coup.out', type=str, help='''Output File.''')

    args = parser.parse_args()

    return args


class CUBE:
    def __init__(self, fname):

        f = open(fname, 'r')
        for i in range(2): f.readline() # echo comment
        tkns = f.readline().split() # number of atoms included in the file followed by the position of the origin of the volumetric data
        self.natoms = int(tkns[0])
        self.origin = np.array([float(tkns[1]),float(tkns[2]),float(tkns[3])])

        # The next three lines give the number of voxels along each axis (x, y, z) followed by the axis vector.
        tkns = f.readline().split() #
        self.NX = int(tkns[0])
        self.X = np.array([float(tkns[1]),float(tkns[2]),float(tkns[3])])
        tkns = f.readline().split() #
        self.NY = int(tkns[0])
        self.Y = np.array([float(tkns[1]),float(tkns[2]),float(tkns[3])])
        tkns = f.readline().split() #
        self.NZ = int(tkns[0])
        self.Z = np.array([float(tkns[1]),float(tkns[2]),float(tkns[3])])

        # The last section in the header is one line for each atom consisting of 5 numbers, the first is the atom number, second (?), the last three are the x,y,z coordinates of the atom center.
        self.atoms = []
        for i in range(self.natoms):
            tkns = map(float, f.readline().split())
            self.atoms.append([tkns[0], tkns[2], tkns[3], tkns[4]])

        # Volumetric data
        self.data = np.zeros((self.NX,self.NY,self.NZ))
        i=0
        for s in f:
            for v in s.split():
                self.data[i/(self.NY*self.NZ), (i/self.NZ)%self.NY, i%self.NZ] = float(v)
                i+=1
        if i != self.NX*self.NY*self.NZ: raise NameError, "FSCK!"


    def dump(self, f):

        # output Gaussian cube into file descriptor "f".
        # Usage pattern: f=open('filename.cube'); cube.dump(f); f.close()
        print >>f, "CUBE file\ngenerated by piton _at_ erg.biophys.msu.ru"
        print >>f, "%4d %.6f %.6f %.6f" % (self.natoms, self.origin[0], self.origin[1], self.origin[2])
        print >>f, "%4d %.6f %.6f %.6f"% (self.NX, self.X[0], self.X[1], self.X[2])
        print >>f, "%4d %.6f %.6f %.6f"% (self.NY, self.Y[0], self.Y[1], self.Y[2])
        print >>f, "%4d %.6f %.6f %.6f"% (self.NZ, self.Z[0], self.Z[1], self.Z[2])
        for atom in self.atoms:
            print >>f, "%s %d %s %s %s" % (atom[0], 0, atom[1], atom[2], atom[3])
        for ix in xrange(self.NX):
            for iy in xrange(self.NY):
                for iz in xrange(self.NZ):
                    print >>f, "%.5e " % self.data[ix,iy,iz],
                    if (iz % 6 == 5): print >>f, ''
                print >>f,  ""


    def mask_sphere(self, R, Cx,Cy,Cz):

        # produce spheric volume mask with radius R and center @ [Cx,Cy,Cz]
        # can be used for integration over spherical part of the volume
        m=0*self.data
        for ix in xrange( int(ceil((Cx-R)/self.X[0])), int(floor((Cx+R)/self.X[0])) ):
            ryz=np.sqrt(R**2-(ix*self.X[0]-Cx)**2)
            for iy in xrange( int(ceil((Cy-ryz)/self.Y[1])), int(floor((Cy+ryz)/self.Y[1])) ):
                rz=np.sqrt(ryz**2 - (iy*self.Y[1]-Cy)**2)
                for iz in xrange( int(ceil((Cz-rz)/self.Z[2])), int(floor((Cz+rz)/self.Z[2])) ):
                    m[ix,iy,iz]=1
        return m


def parse_TrDen(cubfile):

    TrDen1 = CUBE(cubfile)
    
    TrD1 = np.asfortranarray(TrDen1.data)
    
    # structure
    struct1 = np.array(TrDen1.atoms)
    
    # calculate the volume element
    dVx1 = TrDen1.X[0]
    dVy1 = TrDen1.Y[1]
    dVz1 = TrDen1.Z[2]
    
    # Grid points
    NX1 = TrDen1.NX
    NY1 = TrDen1.NY
    NZ1 = TrDen1.NZ
    
    # Origin of the cube
    O1 = TrDen1.origin

    return TrD1, dVx1, dVy1, dVz1, NX1, NY1, NZ1, O1, struct1


def dip_TrDen(TrDen, dVx, dVy, dVz, O):
    '''Calculates a dipole from a Transition Density cube.'''

    NX, NY, NZ = TrDen.shape
    dV = dVx * dVy * dVz
    mu = np.zeros(3)
    TrDen = TrDen * dV

    for i in range(NX):
        for j in range(NY):
            for k in range(NZ):
                p0 = O[0] + i * dVx
                p1 = O[1] + j * dVy
                p2 = O[2] + k * dVz
                mu[0] += p0 * TrDen[i][j][k]
                mu[1] += p1 * TrDen[i][j][k]
                mu[2] += p2 * TrDen[i][j][k]

    return mu


def dipole_chgs(struct, chgs):
    '''Calculates a dipole from a set of coordinates and atomic charges.'''

    return np.dot(struct.T, chgs)


def coup_chgs(struct1, chgs1, struct2, chgs2):
    '''Calculates Electronic Coupling from Transition Charges as described in
    J. Phys. Chem. B, 2006, 110, 17268.'''

    coup = 0
    for i in range(len(struct1)):
        for j in range(len(struct2)):
    
            a1 = struct1[i]
            chg1 = chgs1[i]
    
            a2 = struct2[j]
            chg2 = chgs2[j]
    
            d = np.linalg.norm(a1 - a2)
    
            coup += chg1 * chg2 / d
    
    return coup * au2wn


def coup_PDA(struct1, dip1, struct2, dip2):
    '''Calculates Electronic Coupling according to the Point Dipole
    Approximation.'''

    a1 = struct1[:,0]
    s1 = struct1[:,1:]

    a2 = struct2[:,0]
    s2 = struct2[:,1:]

    com1 = np.dot(s1.T, a1) / np.sum(a1)
    com2 = np.dot(s2.T, a2) / np.sum(a2)

    r = com2 - com1
    rmod = np.linalg.norm(r)
    ur = r / rmod
    dip1mod = np.linalg.norm(dip1)
    udip1 = dip1 / dip1mod
    dip2mod = np.linalg.norm(dip2)
    udip2 = dip2 / dip2mod

    coup = dip1mod * dip2mod * (np.dot(udip1, udip2) - 3 * (np.dot(udip1, ur) * np.dot(udip2, ur))) / rmod**3 

    return coup * au2wn


def banner(text=None, ch='=', length=78):
    """Return a banner line centering the given text.
    
        "text" is the text to show in the banner. None can be given to have
            no text.
        "ch" (optional, default '=') is the banner line character (can
            also be a short string to repeat).
        "length" (optional, default 78) is the length of banner to make.

    Examples:
        >>> banner("Peggy Sue")
        '================================= Peggy Sue =================================='
        >>> banner("Peggy Sue", ch='-', length=50)
        '------------------- Peggy Sue --------------------'
        >>> banner("Pretty pretty pretty pretty Peggy Sue", length=40)
        'Pretty pretty pretty pretty Peggy Sue'
    """
    if text is None:
        return ch * length

    elif len(text) + 2 + len(ch)*2 > length:
        # Not enough space for even one line char (plus space) around text.
        return text

    else:
        remain = length - (len(text) + 2)
        prefix_len = remain / 2
        suffix_len = remain - prefix_len
    
        if len(ch) == 1:
            prefix = ch * prefix_len
            suffix = ch * suffix_len

        else:
            prefix = ch * (prefix_len/len(ch)) + ch[:prefix_len%len(ch)]
            suffix = ch * (suffix_len/len(ch)) + ch[:suffix_len%len(ch)]

        return prefix + ' ' + text + ' ' + suffix


if __name__ == '__main__':

    args = options()
    calctype = args.coup
    outfile = args.output

    start = time.time()
    #
    # Process Transition Charges
    #
    if not calctype or calctype == 'chgs':
        chg1file = args.chg1
        chg2file = args.chg2

        data1 = np.genfromtxt(chg1file)
        data2 = np.genfromtxt(chg2file)

        atoms1 = np.genfromtxt(chg1file,usecols=[0], dtype="|S5")
        atoms1 = map(lambda x: ELEMENTS[x].mass, atoms1)
        struct1 = data1[:,1:4] / au2ang
        fs1 = np.c_[atoms1,struct1]
        chgs1 = data1[:,-1]
        
        atoms2 = np.genfromtxt(chg2file,usecols=[0], dtype="|S5")
        atoms2 = map(lambda x: ELEMENTS[x].mass, atoms2)
        struct2 = data2[:,1:4] / au2ang
        fs2 = np.c_[atoms2,struct2]
        chgs2 = data2[:,-1]

        coupchgs = coup_chgs(struct1, chgs1, struct2, chgs2)
        dip1chgs = dipole_chgs(struct1, chgs1)
        dip1chgsmod = np.linalg.norm(dip1chgs)
        dip2chgs = dipole_chgs(struct2, chgs2)
        dip2chgsmod = np.linalg.norm(dip2chgs)

        coup_PDA_chgs = coup_PDA(fs1, dip1chgs, fs2, dip2chgs)

    #
    # Process Transition Cubes
    #
    if FModule and (not calctype or calctype == 'den'):

        cub1file = args.cub1
        cub2file = args.cub2
        thresh = args.thresh

        TrDenD, dVxD, dVyD, dVzD, NXD, NYD, NZD, OD, structD = parse_TrDen(cub1file)
        TrDenA, dVxA, dVyA, dVzA, NXA, NYA, NZA, OA, structA = parse_TrDen(cub2file)

        dip1den = trden.diptrde(TrDenD, dVxD, dVyD, dVzD, OD)
        dip1denmod = np.linalg.norm(dip1den)
        dip2den = trden.diptrde(TrDenA, dVxA, dVyA, dVzA, OA)
        dip2denmod = np.linalg.norm(dip2den)

        coupden = trden.couptr(TrDenA,dVxA,dVyA,dVzA,OA,TrDenD,dVxD,dVyD,dVzD,OD,thresh)
        coup_PDA_den = coup_PDA(structD, dip1den, structA, dip2den)

    elapsed = (time.time() - start)
    elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed))
    #
    # Write a logfile with results
    #
    with open(outfile, 'w') as f:

        if not calctype or calctype == 'chgs':
            f.write('###################################\n')
            f.write('##  Coupling Transition Charges  ##\n')
            f.write('###################################\n')
            f.write('\n')
            f.write('Coupling calculated from transition charges according to\n')
            f.write('J. Phys. Chem. B, 2006, 110, 17268\n')
            f.write('\n')
            f.write('Donor Structure and Charges:\n')
            f.write(open(chg1file).read())
            f.write('\n')
            f.write('Donor Electric Transition Dipole Moment from Transition Charges in a.u.:\n')
            f.write('%8s %8s %8s %15s\n' % ('x', 'y', 'z', 'norm'))
            f.write('%8.4f %8.4f %8.4f %15.4f\n' % (dip1chgs[0], dip1chgs[1], dip1chgs[2], dip1chgsmod))
            f.write('\n')
            f.write('\n')
            f.write('Acceptor structure and Charges:\n')
            f.write(open(chg2file).read())
            f.write('\n')
            f.write('Acceptor Electric Transition Dipole Moment from Transition Charges in a.u.:\n')
            f.write('%8s %8s %8s %15s\n' % ('x', 'y', 'z', 'norm'))
            f.write('%8.4f %8.4f %8.4f %15.4f\n' % (dip2chgs[0], dip2chgs[1], dip2chgs[2], dip2chgsmod))
            f.write('\n')
            f.write('\n')
            f.write('Electronic Coupling according to PDA from Dipoles from Transition Charges:\n')
            f.write('%-10.2f\n' % coup_PDA_chgs)
            f.write('\n')
            f.write('Electronic Coupling in cm-1:\n')
            f.write('%-10.2f\n' % coupchgs)

        if FModule and (not calctype or calctype == 'den'):
            f.write('\n\n')
            f.write('#####################################\n')
            f.write('##  Coupling Transition Densities  ##\n')
            f.write('#####################################\n')
            f.write('\n')
            f.write('Coupling calculated from transition densities according to\n')
            f.write('J. Phys. Chem. B, 1998, 102, 5378\n')
            f.write('\n')
            f.write('\n')
            f.write('Donor Electric Transition Dipole Moment from Transition Density in a.u.:\n')
            f.write('%8s %8s %8s %15s\n' % ('x', 'y', 'z', 'norm'))
            f.write('%8.4f %8.4f %8.4f %15.4f\n' % (dip1den[0], dip1den[1], dip1den[2], dip1denmod))
            f.write('\n')
            f.write('\n')
            f.write('Acceptor Electric Transition Dipole Moment from Transition Density in a.u.:\n')
            f.write('%8s %8s %8s %15s\n' % ('x', 'y', 'z', 'norm'))
            f.write('%8.4f %8.4f %8.4f %15.4f\n' % (dip2den[0], dip2den[1], dip2den[2], dip2denmod))
            f.write('\n')
            f.write('\n')
            f.write('Electronic Coupling according to PDA from Dipoles from Transition Densities:\n')
            f.write('%-10.2f\n' % coup_PDA_den)
            f.write('\n')
            f.write('Electronic Coupling in cm-1:\n')
            f.write('%-10.2f\n' % coupden)

        if not FModule:
            f.write('\n\n')
            f.write(" WARNING!!!\n")
            f.write(" The Fortran Module could not be loaded.\n")
            f.write(" Coupling from Transition Densities was not computed.\n")

        f.write('\n')
        f.write('\n')
        f.write('#####################\n')
        f.write('##  Results Table  ##\n')
        f.write('#####################\n')
        f.write('\n')
        f.write(' Calculation time: %s\n' % elapsed)
        f.write('\n')
        f.write('# Method          Coupling (cm-1)\n')
        f.write('#--------------------------------\n')

        if not calctype or calctype == 'chgs':
            f.write(' Tr Chgs         %8.2f \n' % coupchgs)
            f.write(' PDA Dip Chgs    %8.2f \n' % coup_PDA_chgs)

        if FModule and (not calctype or calctype == 'den'):
            f.write(' Tr Den          %8.2f \n' % coupden)
            f.write(' PDA Dip Den     %8.2f \n' % coup_PDA_den)
