import numpy as np
import sys as sys
import scipy
import math as math
import scipy.sparse as sps
from scipy.sparse.linalg.dsolve import linsolve
from scipy.sparse import lil_matrix
import time as timing

#------------------------------------------------------------------------------

def NNV(rq,sq):
    NV_0= (1.-rq-sq)*(1.-2.*rq-2.*sq+ 3.*rq*sq)
    NV_1= rq*(2.*rq -1. + 3.*sq-3.*rq*sq-3.*sq**2 )
    NV_2= sq*(2.*sq -1. + 3.*rq-3.*rq**2-3.*rq*sq )
    NV_3= 4.*rq*sq*(-2.+3.*rq+3.*sq)
    NV_4= 4.*(1.-rq-sq)*sq*(1.-3.*rq)
    NV_5= 4.*(1.-rq-sq)*rq*(1.-3.*sq)
    NV_6= 27*(1.-rq-sq)*rq*sq
    return NV_0,NV_1,NV_2,NV_3,NV_4,NV_5,NV_6

def dNNVdr(rq,sq):
    dNVdr_0= -3+4*rq+7*sq-6*rq*sq-3*sq**2
    dNVdr_1= 4*rq-1+3*sq-6*rq*sq-3*sq**2
    dNVdr_2= 3*sq-6*rq*sq-3*sq**2
    dNVdr_3= -8*sq+24*rq*sq+12*sq**2
    dNVdr_4= -16*sq+24*rq*sq+12*sq**2
    dNVdr_5= -8*rq+24*rq*sq+4-16*sq+12*sq**2
    dNVdr_6= -54*rq*sq+27*sq-27*sq**2
    return dNVdr_0,dNVdr_1,dNVdr_2,dNVdr_3,dNVdr_4,dNVdr_5,dNVdr_6

def dNNVds(rq,sq):
    dNVds_0= -3+7*rq+4*sq-6*rq*sq-3*rq**2
    dNVds_1= rq*(3-3*rq-6*sq)
    dNVds_2= 4*sq-1+3*rq-3*rq**2-6*rq*sq
    dNVds_3= -8*rq+12*rq**2+24*rq*sq
    dNVds_4= 4-16*rq-8*sq+24*rq*sq+12*rq**2
    dNVds_5= -16*rq+24*rq*sq+12*rq**2
    dNVds_6= -54*rq*sq+27*rq-27*rq**2
    return dNVds_0,dNVds_1,dNVds_2,dNVds_3,dNVds_4,dNVds_5,dNVds_6

def NNP(rq,sq):
    NP_0=1.-rq-sq
    NP_1=rq
    NP_2=sq
    return NP_0,NP_1,NP_2

def gx(xq,yq,grav):
    return -xq/np.sqrt(xq**2+yq**2)*grav

def gy(xq,yq,grav):
    return -yq/np.sqrt(xq**2+yq**2)*grav

#------------------------------------------------------------------------------

print("-----------------------------")
print("----------fieldstone---------")
print("-----------------------------")

         # Crouzeix-Raviart elements
mV=7     # number of velocity nodes making up an element
mP=3     # number of pressure nodes making up an element
ndofV=2  # number of velocity degrees of freedom per node
ndofP=1  # number of pressure degrees of freedom 

nnp=193785
nel=63590

#nnp=3230462/2
#nel=534363

NfemV=nnp*ndofV     # number of velocity dofs
NfemP=nel*3*ndofP   # number of pressure dofs
Nfem=NfemV+NfemP    # total number of dofs

print ('nel  ', nel)
print ('NfemV', NfemV)
print ('NfemP', NfemP)
print ('Nfem ', Nfem)

pressure_scaling=1e22/6371e3

#---------------------------------------
# 6 point integration coeffs and weights 

nqel=6

nb1=0.816847572980459
nb2=0.091576213509771
nb3=0.108103018168070
nb4=0.445948490915965
nb5=0.109951743655322
nb6=0.223381589678011

qcoords_r=[nb1,nb2,nb2,nb4,nb3,nb4]
qcoords_s=[nb2,nb1,nb2,nb3,nb4,nb4]
qweights=[nb5,nb5,nb5,nb6,nb6,nb6]

grav=9.81

#################################################################
# grid point setup
#################################################################
start = timing.time()

x=np.empty(nnp,dtype=np.float64)     # x coordinates
y=np.empty(nnp,dtype=np.float64)     # y coordinates
r=np.empty(nnp,dtype=np.float64)     # cylindrical coordinate r
theta=np.empty(nnp,dtype=np.float64) # cylindrical coordinate theta 

f = open('../data/raw/GCOORD_lowres.txt', 'r')
counter=0
for line in f:
    line = line.strip()
    columns = line.split()
    if counter==0:
       for i in range(0,nnp):
           x[i]=columns[i]
    if counter==1:
       for i in range(0,nnp):
           y[i]=columns[i]
    counter+=1

x[:]*=1000
y[:]*=1000

for i in range(0,nnp):
    r[i]=np.sqrt(x[i]**2+y[i]**2)
    theta[i]=math.atan2(y[i],x[i])

print("x (min/max): %.4f %.4f" %(np.min(x),np.max(x)))
print("y (min/max): %.4f %.4f" %(np.min(y),np.max(y)))
print("r (min/max): %.4f %.4f" %(np.min(r),np.max(r)))
print("theta (min/max): %.4f %.4f" %(np.min(theta)/np.pi*180,np.max(theta)/np.pi*180))

np.savetxt('gridV.ascii',np.array([x,y]).T,header='# x,y')

print("setup: grid points: %.3f s" % (timing.time() - start))

#################################################################
# connectivity
#################################################################
#
#  P_2^+           P_-1
#
#  02              02
#  ||\\            ||\\
#  || \\           || \\
#  ||  \\          ||  \\
#  05   04         ||   \\
#  || 06 \\        ||    \\
#  ||     \\       ||     \\
#  00==03==01      00======01
#
#################################################################
start = timing.time()
iconV=np.zeros((mV,nel),dtype=np.int32)

f = open('../data/raw/ELEM2NODE_lowres.txt', 'r')
counter=0
for line in f:
    line = line.strip()
    columns = line.split()
    for i in range(0,nel):
        #print (columns[i])
        iconV[counter,i]=float(columns[i])-1
    #print (counter)
    counter+=1

#for iel in range (0,nel):
#    print ("iel=",iel)
#    print ("node 1",iconV[0][iel],"at pos.",x[iconV[0][iel]], y[iconV[0][iel]])
#    print ("node 2",iconV[1][iel],"at pos.",x[iconV[1][iel]], y[iconV[1][iel]])
#    print ("node 3",iconV[2][iel],"at pos.",x[iconV[2][iel]], y[iconV[2][iel]])
#    print ("node 4",iconV[3][iel],"at pos.",x[iconV[3][iel]], y[iconV[3][iel]])
#    print ("node 5",iconV[4][iel],"at pos.",x[iconV[4][iel]], y[iconV[4][iel]])
#    print ("node 6",iconV[5][iel],"at pos.",x[iconV[5][iel]], y[iconV[5][iel]])

#print("iconV (min/max): %d %d" %(np.min(iconV[0,:]),np.max(iconV[0,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[1,:]),np.max(iconV[1,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[2,:]),np.max(iconV[2,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[3,:]),np.max(iconV[3,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[4,:]),np.max(iconV[4,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[5,:]),np.max(iconV[5,:])))
#print("iconV (min/max): %d %d" %(np.min(iconV[6,:]),np.max(iconV[6,:])))

#print (iconV[0:6,0])
#print (iconV[0:6,1])
#print (iconV[0:6,2])

print("setup: connectivity V: %.3f s" % (timing.time() - start))

#################################################################
# build pressure grid (nodes and icon)
#################################################################
start = timing.time()

iconP=np.zeros((mP,nel),dtype=np.int32)
xP=np.empty(NfemP,dtype=np.float64)     # x coordinates
yP=np.empty(NfemP,dtype=np.float64)     # y coordinates

counter=0
for iel in range(0,nel):
    xP[counter]=x[iconV[0,iel]]
    yP[counter]=y[iconV[0,iel]]
    iconP[0,iel]=counter
    counter+=1
    xP[counter]=x[iconV[1,iel]]
    yP[counter]=y[iconV[1,iel]]
    iconP[1,iel]=counter
    counter+=1
    xP[counter]=x[iconV[2,iel]]
    yP[counter]=y[iconV[2,iel]]
    iconP[2,iel]=counter
    counter+=1

np.savetxt('gridP.ascii',np.array([xP,yP]).T,header='# x,y')

#for iel in range (0,nel):
#    print ("iel=",iel)
#    print ("node 0",iconP[0,iel],"at pos.",xP[iconP[0][iel]], yP[iconP[0][iel]])
#    print ("node 1",iconP[1,iel],"at pos.",xP[iconP[1][iel]], yP[iconP[1][iel]])
#    print ("node 2",iconP[2,iel],"at pos.",xP[iconP[2][iel]], yP[iconP[2][iel]])

print("setup: connectivity P: %.3f s" % (timing.time() - start))

#################################################################
# read in material properties
#################################################################
start = timing.time()

rho=np.zeros(nel,dtype=np.float64)  # boundary condition, value
eta=np.zeros(nel,dtype=np.float64)  # boundary condition, value

f = open('../data/raw/Rho_lowres.txt', 'r')
counter=0
for line in f:
    line = line.strip()
    columns = line.split()
    rho[counter]=float(columns[0])*1e21
    counter+=1

print("     -> rho (m,M) %.6e %.6e " %(np.min(rho),np.max(rho)))

f = open('../data/raw/Eta_lowres.txt', 'r')
counter=0
for line in f:
    line = line.strip()
    columns = line.split()
    eta[counter]=float(columns[0])*1e21
    counter+=1

eta[:]=1e22

print("     -> eta (m,M) %.6e %.6e " %(np.min(eta),np.max(eta)))

print("read in density, viscosity: %.3f s" % (timing.time() - start))

#################################################################
# define boundary conditions
#################################################################
start = timing.time()

bc_fix=np.zeros(NfemV,dtype=np.bool)  # boundary condition, yes/no
bc_val=np.zeros(NfemV,dtype=np.float64)  # boundary condition, value
boundary_bottom=np.zeros(nnp,dtype=np.bool) 
boundary_top=np.zeros(nnp,dtype=np.bool)  
boundary_left=np.zeros(nnp,dtype=np.bool) 
boundary_right=np.zeros(nnp,dtype=np.bool)

for i in range(0, nnp):
    if r[i]<4875:
       boundary_bottom[i]=True
       bc_fix[i*ndofV  ] = True ; bc_val[i*ndofV  ] = 0
       bc_fix[i*ndofV+1] = True ; bc_val[i*ndofV+1] = 0
       #r[i]=4871
       #x[i]=r[i]*np.cos(theta[i])
       #y[i]=r[i]*np.sin(theta[i])
    if r[i]>6370.85:
       boundary_top[i]=True
       bc_fix[i*ndofV  ] = True ; bc_val[i*ndofV  ] = 0
       bc_fix[i*ndofV+1] = True ; bc_val[i*ndofV+1] = 0
       #r[i]=6371
       #x[i]=r[i]*np.cos(theta[i])
       #y[i]=r[i]*np.sin(theta[i])
    if theta[i]<0.5237:
       boundary_right[i]=True
       bc_fix[i*ndofV  ] = True ; bc_val[i*ndofV  ] = 0
       bc_fix[i*ndofV+1] = True ; bc_val[i*ndofV+1] = 0
    if theta[i]>2.3561:
       boundary_left[i]=True
       bc_fix[i*ndofV  ] = True ; bc_val[i*ndofV  ] = 0
       bc_fix[i*ndofV+1] = True ; bc_val[i*ndofV+1] = 0

print("define boundary conditions: %.3f s" % (timing.time() - start))

#################################################################
# compute area of elements
#################################################################
start = timing.time()

area=np.zeros(nel,dtype=np.float64) 
NV    = np.zeros(mV,dtype=np.float64)           # shape functions V
dNVdr  = np.zeros(mV,dtype=np.float64)          # shape functions derivatives
dNVds  = np.zeros(mV,dtype=np.float64)          # shape functions derivatives

for iel in range(0,nel):
    for kq in range (0,nqel):
        rq=qcoords_r[kq]
        sq=qcoords_s[kq]
        weightq=qweights[kq]
        NV[0:mV]=NNV(rq,sq)
        dNVdr[0:mV]=dNNVdr(rq,sq)
        dNVds[0:mV]=dNNVds(rq,sq)
        jcb=np.zeros((2,2),dtype=np.float64)
        for k in range(0,mV):
            jcb[0,0] += dNVdr[k]*x[iconV[k,iel]]
            jcb[0,1] += dNVdr[k]*y[iconV[k,iel]]
            jcb[1,0] += dNVds[k]*x[iconV[k,iel]]
            jcb[1,1] += dNVds[k]*y[iconV[k,iel]]
        jcob = np.linalg.det(jcb)
        area[iel]+=jcob*weightq
    if area[iel]<0: 
       for k in range(0,mV):
           print (x[iconV[k,iel]],y[iconV[k,iel]])
   #    print(iel,iconV[:,iel])

print("     -> area (m,M) %.6e %.6e " %(np.min(area),np.max(area)))
print("     -> total area %.6f " %(area.sum()))
print("     -> total area %.6f " %(105./360.*np.pi*(6371e3**2-4871e3**2)   ))

print("compute elements areas: %.3f s" % (timing.time() - start))

#####################################################################
# plot of solution
#####################################################################
# the 7-node P2+ element does not exist in vtk, but the 6-node one 
# does, i.e. type=22. 

if True:
    vtufile=open('solution.vtu',"w")
    vtufile.write("<VTKFile type='UnstructuredGrid' version='0.1' byte_order='BigEndian'> \n")
    vtufile.write("<UnstructuredGrid> \n")
    vtufile.write("<Piece NumberOfPoints=' %5d ' NumberOfCells=' %5d '> \n" %(nnp,nel))
    #####
    vtufile.write("<Points> \n")
    vtufile.write("<DataArray type='Float32' NumberOfComponents='3' Format='ascii'> \n")
    for i in range(0,nnp):
        vtufile.write("%10e %10e %10e \n" %(x[i],y[i],0.))
    vtufile.write("</DataArray>\n")
    vtufile.write("</Points> \n")
    #####
    vtufile.write("<CellData Scalars='scalars'>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='area' Format='ascii'> \n")
    for iel in range (0,nel):
        vtufile.write("%10e\n" % (area[iel]))
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='density' Format='ascii'> \n")
    for iel in range (0,nel):
        vtufile.write("%10e\n" % (rho[iel]))
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='viscosity' Format='ascii'> \n")
    for iel in range (0,nel):
        vtufile.write("%10e\n" % (eta[iel]))
    vtufile.write("</DataArray>\n")
    #--

    vtufile.write("</CellData>\n")
    #####
    vtufile.write("<PointData Scalars='scalars'>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='r' Format='ascii'> \n")
    for i in range(0,nnp):
        vtufile.write("%10e \n" %r[i])
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='theta (deg)' Format='ascii'> \n")
    for i in range(0,nnp):
        vtufile.write("%10e \n" %(theta[i]/np.pi*180.))
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='fix_u' Format='ascii'> \n")
    for i in range(0,nnp):
        if bc_fix[i*2]:
           val=1
        else:
           val=0
        vtufile.write("%10e \n" %val)
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Float32' Name='fix_v' Format='ascii'> \n")
    for i in range(0,nnp):
        if bc_fix[i*2+1]:
           val=1
        else:
           val=0
        vtufile.write("%10e \n" %val)
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("</PointData>\n")
    #####
    vtufile.write("<Cells>\n")
    #--
    vtufile.write("<DataArray type='Int32' Name='connectivity' Format='ascii'> \n")
    for iel in range (0,nel):
        vtufile.write("%d %d %d %d %d %d\n" %(iconV[0,iel],iconV[1,iel],iconV[2,iel],iconV[5,iel],iconV[3,iel],iconV[4,iel]))
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Int32' Name='offsets' Format='ascii'> \n")
    for iel in range (0,nel):
        vtufile.write("%d \n" %((iel+1)*6))
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("<DataArray type='Int32' Name='types' Format='ascii'>\n")
    for iel in range (0,nel):
        vtufile.write("%d \n" %22)
    vtufile.write("</DataArray>\n")
    #--
    vtufile.write("</Cells>\n")
    #####
    vtufile.write("</Piece>\n")
    vtufile.write("</UnstructuredGrid>\n")
    vtufile.write("</VTKFile>\n")
    vtufile.close()



print("-----------------------------")
print("------------the end----------")
print("-----------------------------")




