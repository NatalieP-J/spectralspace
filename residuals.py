import apogee.tools.read as apread
from apogee.tools import bitmask
import numpy as np
try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib.colors import LogNorm
        import matplotlib
        import window as wn
except RuntimeError as e:
        if 'display' in e:
                print 'Running remotely, plot generation will fail if not turned off'
#import window as wn
import os
import access_spectrum as acs
import reduce_dataset as rd
import polyfit as pf
#import apogee.spec.plot as splot
from read_clusterdata import read_caldata
import time

badcombpixmask= bitmask.badpixmask()+2**bitmask.apogee_pixmask_int("SIG_SKYLINE")

elems = ['Al','Ca','C','Fe','K','Mg','Mn','Na','Ni','N','O','Si','S','Ti','V']

GCs = ['M107','M13','M15','M2','M3','M5','M53','M71','M92','N5466']
OCs = ['M67','N188','N2158','N2420','N4147','N6791','N6819','N7789']

outdirs = {'pkl':'pickles/',
		   'fit':'fitplots/',
		   'res':'residual_plots/'}

readfn = {'clusters' : read_caldata,
		  'OCs': read_caldata,
		  'GCs': read_caldata,
		  'red_clump' : apread.rcsample}

fitvars = {'clusters':['TEFF'],
		   'OCs':['TEFF'],
		   'GCs':['TEFF'],
		   'red_clump':['TEFF','LOGG','FE_H']}

alphas = {'clusters':1,
		   'OCs':1,
		   'GCs':1,
		   'red_clump':0.3}

aspcappix = 7214

windowinfo = 'windowinfo.pkl'
if not os.path.isfile(windowinfo):
	totalw = np.zeros(aspcappix)
	elemwindows = {}
	windowPixels = {}
	tophats = {}
	for elem in elems:
		w = wn.read(elem,dr = 12,apStarWavegrid = False)
		elemwindows[elem] = w
		windowPixels[elem] = np.where(w != 0)
		tophats[elem] = wn.tophat(elem,dr=12,apStarWavegrid=False)
		totalw += w
	acs.pklwrite(windowinfo,[elemwindows,totalw,windowPixels,tophats])
elif os.path.isfile(windowinfo):
	elemwindows,totalw,windowPixels,tophats = acs.pklread(windowinfo)

def getSpectra(data,name,ind,readtype,gen=False):
	if os.path.isfile(name) and not gen:
		return acs.pklread(name)
	elif not os.path.isfile(name) or gen:
		if readtype == 'asp':
			spectra = acs.get_spectra_asp(data,ext = ind,header = False)
		elif readtype == 'ap':
			spectra = acs.get_spectra_ap(data,ext = ind,header = False, indx = 1)
		else:
			print 'Choose asp or ap as type.'
		acs.pklwrite(name,spectra)
		return spectra

def indepOrdered(indeps,length):
	indepOrder = ()
	for indep in indeps:
		arr = np.linspace(min(indep),max(indep),length)
		indepOrder+=(arr,)
	return indepOrder

def pixPlot(pix,indeps,inames,savename,specs,errs,res,order,p,samptype,maskarr):
	nomask = np.where((maskarr!=-1))
        mask = np.where(maskarr==-1)
        rpl = np.where((errs[nomask] > 0.1))
	bpl = np.where((errs[nomask] < 0.1))
	indepOrder = indepOrdered(indeps,1000)
	plt.figure(figsize = (16,14))
	for loc in range(len(indeps)):
		plt.subplot2grid((2,len(indeps)+1),(0,loc))
		plt.errorbar(indeps[loc][nomask][rpl],specs[nomask][rpl],yerr=errs[nomask][rpl],fmt='.',color='red')
		plt.plot(indeps[loc][nomask][bpl],specs[nomask][bpl],'.',color = 'blue',alpha = alphas[samptype])
                plt.plot(indeps[loc][mask],specs[mask],'.',color = 'magenta',alpha = alphas[samptype])
		plt.plot(indepOrder[loc],pf.poly(p,indepOrder,order=order),color='k',linewidth = 3)
		plt.xlabel(inames[loc])
		plt.ylabel('Pixel {0}'.format(pix))
		plt.subplot2grid((2,len(indeps)+1),(1,loc))
                plt.plot(indeps[loc][mask],res[mask],'.',color='magenta',alpha = alphas[samptype])
		plt.plot(indeps[loc][nomask][rpl],res[nomask][rpl],'.',color='red')
		plt.plot(indeps[loc][nomask][bpl],res[nomask][bpl],'.',color='blue',alpha=alphas[samptype])
		plt.xlabel(inames[loc])
		plt.ylabel('Fit residuals')
		plt.ylim(min(res),max(res))
	plt.subplot2grid((2,len(indeps)+1),(0,len(indeps)))
	plt.semilogx(errs[nomask][bpl],res[nomask][bpl],'.',color = 'blue',alpha = alphas[samptype])
        plt.semilogx(errs[nomask][rpl],res[nomask][rpl],'.',color = 'red')
        plt.semilogx(errs[mask],res[mask],'.',color='magenta',alpha = alphas[samptype])
	plt.xlabel('Uncertainty in Pixel {0}'.format(pix))
	plt.ylabel('Fit residuals')
	plt.ylim(min(res),max(res))
	ws = [item for item in windowPixels.values() if pix in item[0]][0]
	elem = [item for item in windowPixels.keys() if ws == windowPixels[item]][0]
	plt.suptitle(elem+' Pixel')
	plt.tight_layout()
	plt.savefig(savename)
	plt.close()

def doubleResidualHistPlot(elem,residual,sigma,savename,bins = 50):
	plt.figure(figsize = (12,10))
	Rhist,Rbins = np.histogram(residual,bins = bins,range = (-0.1,0.1))
	Ghist,Gbins = np.histogram(sigma,bins = bins,range = (-0.1,0.1))
	plt.bar(Rbins[:-1],Rhist/float(max(Rhist)),width = (Rbins[1]-Rbins[0]))
	plt.bar(Gbins[:-1],Ghist/float(max(Ghist)),width = (Gbins[1]-Gbins[0]),color = 'g',alpha = 0.75)
	plt.xlim(-0.1,0.1)
	plt.xlabel('Weighted scatter')
	plt.ylabel('Star count normalized to peak')
	plt.title(elem)
	plt.savefig(savename)
	plt.close()

class Sample:
	def __init__(self,sampletype,seed,order,genstep,label = 0,low = 0,up = 0,fontsize = 18):
		self.type = sampletype
		self.overdir = './'+sampletype+'/'
		self.seed = seed
		np.random.seed(seed)
		self.order = order
		self.label = label
		self.low = low
		self.up = up
		self.genstep = genstep
		if label != 0:
			self.specname = self.overdir+outdirs['pkl']+'spectra_{0}_u{1}_d{2}.pkl'.format(label,low,up)
			self.errname = self.overdir+outdirs['pkl']+'errs_{0}_u{1}_d{2}.pkl'.format(label,low,up)
			self.maskname = self.overdir+outdirs['pkl']+'mask_{0}_u{1}_d{2}.pkl'.format(label,low,up)
			self.disname = self.overdir+outdirs['pkl']+'discard_order{0}_{1}_u{2}_d{3}.pkl'.format(order,label,low,up)
			self.failname = self.overdir+outdirs['pkl']+'fails_order{0}_{1}_u{2}_d{3}.pkl'.format(order,label,low,up)
		elif label == 0:
			self.specname = self.overdir+outdirs['pkl']+'spectra.pkl'
			self.errname = self.overdir+outdirs['pkl']+'errs.pkl'
			self.maskname = self.overdir+outdirs['pkl']+'mask.pkl'
			self.disname = self.overdir+outdirs['pkl']+'discard_order{0}.pkl'.format(order)
			self.failname = self.overdir+outdirs['pkl']+'fails_order{0}.pkl'.format(order)
		

		font = {'family' : 'serif',
        		'weight' : 'normal',
        		'size'   : fontsize}

		try:
                        matplotlib.rc('font', **font)
                except NameError:
                        print 'plotting turned off'

	def paramname(self,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['pkl']+'fitparam_order{0}_{1}_u{2}_d{3}.pkl'.format(self.order,self.label,self.low,self.up)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['pkl']+'fitparam_order{0}.pkl'.format(self.order)
		elif cluster != False:
			return self.overdir+outdirs['pkl']+'{0}_fitparam_order{1}.pkl'.format(cluster,self.order)

	def resname(self,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['pkl']+'residuals_order{0}_{1}_u{2}_d{3}.pkl'.format(self.order,self.label,self.low,self.up)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['pkl']+'residuals_order{0}.pkl'.format(self.order)
		elif cluster != False:
			return self.overdir+outdirs['pkl']+'{0}_residuals_order{1}.pkl'.format(cluster,self.order)

	def signame(self,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['pkl']+'sigma_order{0}_{1}_u{2}_d{3}_seed{4}.pkl'.format(self.order,self.label,self.low,self.up,self.seed)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['pkl']+'sigma_order{0}_seed{1}.pkl'.format(self.order,self.seed)
		elif cluster != False:
			return self.overdir+outdirs['pkl']+'{0}_sigma_order{1}_seed{2}.pkl'.format(cluster,self.order,self.seed)


	def residElemName(self,elem,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['pkl']+'{0}_resids_order{1}_{2}_u{3}_d{4}.pkl'.format(elem,self.order,self.label,self.low,self.up)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['pkl']+'{0}_resids_order{1}.pkl'.format(elem,self.order)
		elif cluster != False:
			return self.overdir+outdirs['pkl']+'{0}_{1}_resids_order{0}.pkl'.format(cluster,elem,self.order)

	def sigmaElemName(self,elem,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['pkl']+'{0}_sigma_order{1}_{2}_u{3}_d{4}_seed{5}.pkl'.format(elem,self.order,self.label,self.low,self.up,self.seed)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['pkl']+'{0}_sigma_order{1}_{2}.pkl'.format(elem,self.order,self.seed)
		elif cluster != False:
			return self.overdir+outdirs['pkl']+'{0}_{1}_sigma_order{2}_{3}.pkl'.format(cluster,elem,self.order,self.seed)

	def fitPlotName(self,pix,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['fit']+'pix{0}fit_order{1}_{2}_u{3}_d{4}.png'.format(pix,self.order,self.label,self.low,self.up)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['fit']+'pix{0}fit_order{1}.png'.format(pix,self.order)
		elif cluster != False:
			return self.overdir+outdirs['fit']+'{0}_pix{1}fit_order{2}.png'.format(cluster,pix,self.order)

	def residhistElemPlotName(self,elem,cluster=False):
		if self.label != 0 and not cluster:
			return self.overdir+outdirs['res']+'{0}_residhist_order{1}_{2}_u{3}_d{4}_seed{5}.png'.format(elem,self.order,self.label,self.low,self.up,self.seed)
		elif self.label == 0 and not cluster:
			return self.overdir+outdirs['res']+'{0}_residhist_order{1}_{2}.png'.format(elem,self.order,self.seed)
		elif cluster != False:
			return self.overdir+outdirs['res']+'{0}_{1}_residhist_order{2}_{3}.png'.format(cluster,elem,self.order,self.seed)

	def makeDirec(self):
		for outdir in outdirs.values():
			if not os.path.isdir(self.overdir+outdir):
				os.system('mkdir '+self.overdir+outdir)

	def getData(self):
		self.data = readfn[self.type]()
		if self.label != 0:
			sindx = rd.slice_data(self.data,[self.label,self.low,self.up])
			self.data = self.data[sindx]
		if self.type == 'OCs':
			sindx = np.where(self.data['CLUSTER'] in OCs)
			self.data = self.data[sindx]
		if self.type == 'GCs':
			sindx = np.where(self.data['CLUSTER'] in GCs)
			self.data = self.data[sindx]
		if self.type != 'red_clump':
			self.data['APOGEE_ID'] = self.data['ID']	
		self.specs = getSpectra(self.data,self.specname,1,'asp',gen=self.genstep['specs'])
		self.errs = getSpectra(self.data,self.errname,2,'asp',gen=self.genstep['specs'])
		self.bitmask = getSpectra(self.data,self.maskname,3,'ap',gen=self.genstep['specs'])
		if len(self.specs) > 1:
			if isinstance(self.specs[1],list):
				self.data = self.data[self.specs[1]]
				self.specs = self.specs[0]
				self.errs = self.errs[0]
				self.bitmask = self.mask[0][self.mask[1]]
                self.mask = np.zeros(self.specs.shape)

	def snrCorrect(self):
		SNR = self.specs/self.errs
		toogood = np.where(SNR > 200.)
		self.errs[toogood] = self.specs[toogood]/200.

        def snrCut(self):
                SNR = self.specs/self.errs
                toobad = np.where(SNR < 1.)
                self.mask[toobad] = -1

	def maskData(self):
		maskregions = np.where((self.bitmask != 0))
                self.mask[maskregions] = -1
		maskregions = np.where((self.specs < 1e-5))
                self.mask[maskregions] = -1


	def pixFit(self,pix,cluster=False):
		nomask = np.where(self.mask[:,pix] != -1)
                mask = np.where(self.mask[:,pix] == -1)
		res = np.array([-1]*(len(self.specs[:,pix])),dtype=np.float64)
		allindeps = ()
                for fvar in fitvars[self.type]:
                        allindeps += (self.data[fvar],)
                indeps = ()
		for fvar in fitvars[self.type]:
			indeps += (self.data[fvar][nomask],)
		try:
			p = pf.regfit(indeps,self.specs[:,pix][nomask],err = self.errs[:,pix][nomask],order = self.order)
			res[nomask] = self.specs[:,pix][nomask] - pf.poly(p,indeps,order=self.order)
                        res[mask] = self.specs[:,pix][mask] - pf.poly(p,allindeps,order = self.order)[mask]
			if self.genstep['autopixplot'] and not self.genstep['pixplot']:
				if totalw[pix] != 0:
					pixPlot(pix,allindeps,fitvars[self.type],
							self.fitPlotName(pix,cluster=cluster),
							self.specs[:,pix],self.errs[:,pix],res,
							self.order,p,self.type,self.mask[:,pix])
			elif self.genstep['pixplot']:
				pixPlot(pix,allindeps,fitvars[self.type],
						self.fitPlotName(pix,cluster=cluster),
						self.specs[:,pix],self.errs[:,pix],res,
						self.order,p,self.type,self.mask[:,pix])
		except np.linalg.linalg.LinAlgError as e:
			p = np.zeros(self.order*len(indeps)+1)
			print cluster,pix,len(nomask[0])
			print e
		return res,p

	def allPixFit(self,cluster=False):
		if os.path.isfile(self.resname(cluster=cluster)) and not self.genstep['pixfit']:
			self.residual = acs.pklread(self.resname(cluster=cluster))
		elif not os.path.isfile(self.resname(cluster=cluster)) or self.genstep['pixfit']:
			ress = []
			params = []
			for pix in range(aspcappix):
				res,param = self.pixFit(pix,cluster=cluster)
				ress.append(res)
				params.append(param[0])
			self.residual = np.array(ress)
			self.params = np.array(params)
			acs.pklwrite(self.resname(cluster=cluster),self.residual)
			acs.pklwrite(self.paramname(cluster=cluster),self.params)

	def randomSigma(self,pix):
		nomask = np.where(self.mask[:,pix] != -1)
		sigma = np.array([-1]*(len(self.specs[:,pix])),dtype = np.float64)
		for s in nomask:
			sigma[s] = np.random.normal(loc = 0,scale = self.errs[:,pix][s])
		return sigma

	def allRandomSigma(self,cluster=False):
		if os.path.isfile(self.signame(cluster=cluster)) and not self.genstep['ransig']:
			self.sigma = acs.pklread(self.signame(cluster=cluster))
		elif not os.path.isfile(self.signame(cluster=cluster)) or self.genstep['ransig']:
			sigs = []
			for pix in range(aspcappix):
				sig = self.randomSigma(pix)
				sigs.append(sig)
			self.sigma = np.array(sigs)
			acs.pklwrite(self.signame(cluster=cluster),self.sigma)

	def weighting(self,arr,elem,name):
		if os.path.isfile(name) and not self.genstep['weight']:
			return acs.pklread(name)
		elif not os.path.isfile(name) or self.genstep['weight']:
			w = elemwindows[elem]
			nw = pf.normweights(w)
			weighted = []
			for star in range(len(arr[0])):
                                nomask = np.where(self.mask[star][tophats[elem]] != -1)
				weighted.append(pf.genresidual(nw[tophats[elem]][nomask],arr[:,star][tophats[elem]][nomask]))
			weighted = np.array(weighted)
			acs.pklwrite(name,weighted)
			return weighted






