import sys
import numpy as np
import math
from utilities.matrices import *
from copy import deepcopy


class ArcLengthParametrizer(object):
    """A python utility used to reparametrize a one dimensional curve. We
    assume that the curve parameter goes from 0 to 1 and we want to find the
    new curve with an arclength parametrization. The new parametrization will
    go again from 0 to 1 but with a constant velocity = L which is the overall
    length of the curve that we assume to be a constant.
    For the time-being we don't consider any time dependence. The curve is only
    space dependent. If you have something time dependent you are asked to query
    this class time by time. We assume that the curve is parametrized from 0 to 1.
    """
    def __init__(self, vector_space, init_control_points,length_constraint = 0, constrained = 0, arcfactor = 10):
		"""The constructor needs an initital curve and we ask for a factor that we will use to 
		numerically approximate the arclength, therefore we have called it arcfactor. We expect the
		curve to be composed by a vector space and a control point array. The length_constraint 
		specify the constraint on the curve length.
		"""
		self.all_init_control_points = np.asarray(init_control_points)
		self.vector_space = AffineVectorSpace(vector_space)
		self.arcfactor = arcfactor
		self.n_dofs = self.vector_space.n_dofs
		#print self.init_control_points.shape
		self.dim = self.all_init_control_points.shape[-1]
		self.all_new_control_points = np.empty_like(self.all_init_control_points)
		#print self.init_control_points.shape
		self.orig_shape = self.all_init_control_points.shape
		self.length_constraint = length_constraint
		self.constrained = constrained 
		if(len(self.orig_shape) > 2):
			print "We will interpret wathever there is between first and last indeces of init_control_points shape as a list among which reparametrize"
			self.param_list = np.array(self.orig_shape[1:-1])
			self.param_tot = np.prod(self.param_list)
			#print self.param_tot, self.param_list
			self.all_init_control_points = self.all_init_control_points.reshape((self.orig_shape[0],self.param_tot,self.orig_shape[-1]))
			self.all_new_control_points = self.all_new_control_points.reshape((self.orig_shape[0],self.param_tot,self.orig_shape[-1]))
			self.lengths = np.empty(self.param_tot)
		else:
			self.curve = self.vector_space.element(self.all_init_control_points)
			self.param_tot = 0
			self.lengths = np.array([0.])


		#print np.squeeze(self.curve(np.array([0.2,0.5]))).shape, np.array([0.2,0.5]).shape
		#self.curve_der = self.vector_space.element_der(self.init_control_points,1)

    def reparametrize(self):		
		"""This function compute the reparametrization. It queries the LS_assembler and LS_solver to compute
		the new knot vector that you can use to build an arclength reparametrized curve. """
		print "Starting the reparametrization"
		if(self.param_tot != 0):
			if(self.length_constraint == 3):
				print "WE UNDO THE REPARAM. DEAL WITH IT"
				for i in range(self.param_tot):
					self.init_control_points = np.squeeze(self.all_init_control_points[:,i,:])
					self.curve = self.vector_space.element(self.init_control_points)
					self.compute_arclength(i)

				self.all_new_control_points = self.all_init_control_points
				self.max_length = np.max(self.lengths)
				for i in range(self.param_tot):
					self.new_control_points = self.all_new_control_points[:,i,:]
					self.length_fixer(self.max_length)
					self.all_new_control_points[:,i,:] = self.new_control_points
			else:
				for i in range(self.param_tot):
					self.init_control_points = np.squeeze(self.all_init_control_points[:,i,:])
					self.curve = self.vector_space.element(self.init_control_points)
					self.compute_arclength(i)
					if(self.constrained == 1):
						print "Assembling the LS constrained system"
						self.constrained_reparametrization_LS_assembler(i)
						print "Solving the constrained system"
						self.new_control_points = np.asarray(self.constrained_reparametrization_LS_solver())
					else:
						print "Assembling the LS system"
						self.reparametrization_LS_assembler(i)
						print "Solving the system"
						self.new_control_points = np.asarray(self.reparametrization_LS_solver())
					#At this point we can impose that each reparametrization maintains the same length.
					if (self.length_constraint == 1):
						self.length_fixer(self.lengths[i])
					self.all_new_control_points[:,i,:] = self.new_control_points
				if(self.length_constraint == 2):
					self.max_length = np.max(self.lengths)
					for i in range(self.param_tot):
						self.new_control_points = self.all_new_control_points[:,i,:]
						self.length_fixer(self.max_length)
						self.all_new_control_points[:,i,:] = self.new_control_points



			self.all_new_control_points = self.all_new_control_points.reshape(self.orig_shape)
		else:
			self.init_control_points = self.all_init_control_points
			self.compute_arclength()
			print "Assembling the LS system"
			self.reparametrization_LS_assembler()
			print "Solving the system"
			self.new_control_points = np.asarray(self.reparametrization_LS_solver())
			if (self.length_constraint == 1):
				self.length_fixer(self.lengths[0])
				self.length_fixer(self.lengths[0]);
			self.all_new_control_points = self.new_control_points

		return self.all_new_control_points

    def compute_arclength(self,param=0):
		"""This function compute the overall length of the curve. We choose to do this
		in a very easy way. We consider a very large amount of points and we compute the
		length of the original curve considering it as piecewise rectilinear function.
		We return a numpy array holding the position in the old parametrization and the
		length of the curve at that point."""
		self.points_s = np.matrix([np.linspace(0, 1, self.arcfactor * self.arcfactor * self.n_dofs), 
								 np.zeros(self.arcfactor * self.arcfactor * self.n_dofs)])
		self.points_s = self.points_s.transpose()
		self.points_s[0,1] = 0.
		#all_points_trial = self.curve(np.array(self.points_s[:,0]).transpose())
		#print  np.array(self.points_s[:,0]).transpose().shape, all_points_trial.shape

		all_points = np.asmatrix(np.squeeze(self.curve(np.array(self.points_s[:,0])))).transpose()
		#all_points = all_points.transpose()
		#print all_points.shape#, np.squeeze(all_points).shape, np.array(self.points_s[:,0]).shape
		all_points_diff = np.diff(all_points,1,0);
		#print all_points_diff.shape, all_points.shape
		#print self.points_s.shape, all_points_diff.shape
		for i in range(1, self.points_s.shape[0]):
			self.points_s[i,1] = np.linalg.norm(all_points_diff[i-1,:]) + self.points_s[i-1,1]
		self.lengths[param] = self.points_s[-1,1]
		return self.points_s

    def find_s(self, sval):
		"""We call sval the arclength value we are quering. This function returns the tval, i.e.
		the value of the original parameter for which the desired arclength is achieved.
		We search over the array self.points_s for the closest arclength value to the desired 
		sval."""
		#error = 1.
		index = np.argmin(np.abs(self.points_s[:,1] - sval))
		return self.points_s[index,0]
		# for i in range(0, self.points_s.shape[0]):
		# 	if(abs(self.points_s[i,1] - sval) < error):
		# 		error = abs(self.points_s[i,1] - sval)
		# 		tval = self.points_s[i,0]
		# return tval

    def reparametrization_LS_assembler(self,parameter=0):
		"""In this function we compute the arclength reparametrization by mean of a Least Square 
		problem."""
		
		s_array = np.linspace(0, self.points_s[-1,1], self.arcfactor * self.n_dofs)
		#self.point_ls = list()
		self.point_ls = np.asmatrix(np.zeros([s_array.shape[0],self.dim + 2]))
		tval = np.zeros(s_array.shape[0])
		sval = np.linspace(0,1,s_array.shape[0])
		for i in range(0, s_array.shape[0]):
			tval[i] = self.find_s(s_array[i])
			#rint tval
			# The curve should have a value( or __call__ if prefered) method that we can query to know its value in space
		self.point_ls[:,0:self.dim] = np.squeeze(self.curve(tval).transpose())
		self.rhsinit = np.squeeze(self.curve(tval).transpose())
		#self.point_ls[:,self.dim] = s_array[:,np.newaxis]
		self.point_ls[:,self.dim] = tval[:,np.newaxis]
			# In point_ls we store the value in space, the s_array and the tval obtained
			#self.point_ls.append([cval, s_array[i], tval])

		#self.point_ls = np.array(self.point_ls)
		# We compute the number of elements in the system rectangular matrix(Bmatrix), it will have dim*s_array.shape[0] rows and dim*nknot columns.
		# We want it to be rectangular because we are approximating its resilution so we search for something that solves the reparametrization in a 
		# least square sense.
		#Bmatrixnumelem = self.dim * s_array.shape[0] * self.n_dofs * self.dim
		#self.matrixB = np.zeros(Bmatrixnumelem).reshape(self.dim * s_array.shape[0], self.n_dofs * self.dim)
		#self.rhsinit = np.zeros(self.dim * s_array.shape[0])
		if(parameter==0):
			self.matrixB = interpolation_matrix(self.vector_space, sval)

		# for i in range(0, s_array.shape[0]):
		# 	for j in range(0, self.n_dofs):
		# 		for d in range(0, self.dim):
		# 			self.matrixB[self.dim * i + d, j * self.dim + d] = computation_matrix[i,j]#self.vector_space.basis(j)(self.point_ls[i, self.dim])

		# 	for d in range(0, self.dim):
		# 		self.rhsinit[self.dim * i + d] = self.point_ls[i,d]


    def constrained_reparametrization_LS_assembler(self,parameter=0):
		"""In this function we compute the arclength reparametrization by mean of a Least Square 
		problem. We need to apply some constraints to our system in order to efficiently reparametrize
		our curve."""
		
		s_array = np.linspace(0, self.points_s[-1,1], self.arcfactor * self.n_dofs)
		self.point_ls = np.asmatrix(np.zeros([s_array.shape[0],self.dim + 2]))
		tval = np.zeros(s_array.shape[0])
		sval = np.linspace(0,1,s_array.shape[0])
		for i in range(0, s_array.shape[0]):
			tval[i] = self.find_s(s_array[i])
		self.point_ls[:,0:self.dim] = np.squeeze(self.curve(tval).transpose())
		self.rhsinit = np.squeeze(self.curve(tval).transpose())
		self.point_ls[:,self.dim] = tval[:,np.newaxis]
		self.rhsx = np.zeros((self.n_dofs + 1, 1))
		self.rhsy = np.zeros((self.n_dofs + 2, 1))
		self.rhsz = np.zeros((self.n_dofs + 2, 1))
		if(parameter==0):
			self.matrixBx = np.zeros((self.n_dofs + 1, self.n_dofs  + 1))
			self.matrixByz = np.zeros((self.n_dofs  + 2, self.n_dofs  + 2))
			self.matrixBtB = np.zeros((self.n_dofs  , self.n_dofs ))
			self.matrixConstraints = np.zeros((2, self.n_dofs))
			self.matrixB = interpolation_matrix(self.vector_space, sval)			
			self.matrixBtB = np.dot(self.matrixB.transpose(), self.matrixB)
			self.matrixConstraints[0,0] = 1.
			self.matrixConstraints[1,0] = 1.
			self.matrixConstraints[1,1] = -1.
			self.matrixBx[:-1,:-1] = self.matrixBtB
			self.matrixBx[-1,:-1] = self.matrixConstraints[0,:]
			self.matrixBx[:-1,-1] = self.matrixConstraints.transpose()[:,0]#,np.newaxis]
			self.matrixByz[:-2,:-2] = self.matrixBtB
			self.matrixByz[-2:,:-2] = self.matrixConstraints[:,:]
			self.matrixByz[:-2,-2:] = self.matrixConstraints.transpose()[:,:]
		self.rhsx[:-1,0]=np.dot(self.matrixB.transpose(), self.rhsinit[:,0])
		self.rhsy[:-2,0]=np.dot(self.matrixB.transpose(), self.rhsinit[:,1])
		self.rhsz[:-2,0]=np.dot(self.matrixB.transpose(), self.rhsinit[:,2])
        
    def reparametrization_LS_solver(self):
		"""In this method we solve the LS system assembled before. The result should be the new knot_vector that
		will form the arclength reparametrized curve."""
		#print self.matrixB.shape, self.rhsinit.shape
		res = np.linalg.lstsq(self.matrixB, self.rhsinit)
		#print res[0]
		return res[0]


    def constrained_reparametrization_LS_solver(self):
		"""In this method we solve the constrained LS system assembled before. The result should be the new knot_vector that
		will form the arclength reparametrized curve. It should respect the constraints we have applied"""
		resx = np.linalg.solve(self.matrixBx, self.rhsx)
		resy = np.linalg.solve(self.matrixByz, self.rhsy)
		resz = np.linalg.solve(self.matrixByz, self.rhsz)
		#print resx.shape, resy.shape, resz.shape
		#return c_[resx[:-1], resy[:-2], resz[:-2]]
		return np.squeeze(np.array([resx[:-1], resy[:-2], resz[:-2]])).transpose()



    def length_fixer(self,prescribed_length=1):
		"""In this method we modify the arclength parametrization we have obtained in order to get a prescribe length.
		By default we fix this to the original length of the curve. We fix the first control point and then we dilatates
		all the others."""
		cp0 = deepcopy(self.new_control_points[0])
		self.new_control_points -= cp0
		# Here we need to compute the overall length of the reparametrized curve in order to rescale it properly
		new_curve = self.vector_space.element(self.new_control_points)
		self.new_points_s = np.matrix([np.linspace(0, 1, self.arcfactor * self.arcfactor * self.n_dofs), 
								 np.zeros(self.arcfactor * self.arcfactor * self.n_dofs)])
		self.new_points_s = self.new_points_s.transpose()
		self.new_points_s[0,1] = 0.
		all_points = np.asmatrix(np.squeeze(new_curve(np.array(self.new_points_s[:,0])))).transpose()
		all_points_diff = np.diff(all_points,1,0);
		for i in range(1, self.new_points_s.shape[0]):
			self.new_points_s[i,1] = np.linalg.norm(all_points_diff[i-1,:]) + self.new_points_s[i-1,1]
		actual_length = self.new_points_s[-1,1]
	#	print actual_length, prescribed_length
		self.new_control_points *= prescribed_length / actual_length
		self.new_control_points += cp0
		return self.new_control_points

#	def length_fixer(self,prescribed_length=1):	

