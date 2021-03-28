import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as mani
from enum import Enum

import os	## for relative imports
script_dir = os.path.dirname(__file__)
to_path = lambda p : os.path.relpath(p)

import time
T0 = time.time()
PI = 3.1415926535

class Trig(Enum):
    Ascending = 0
    Descending = 1

class Ring:
    def __init__(self, n = 1):
        self.x = []
        self.i = -1
        self.full = False
        self.n = n
        
    def set_n(self, n):
        if n > self.n: self.full = False
        if n < self.n:
            if self.full or self.i > n:
                self.x = x[:n]
                
            self.full = self.full or self.i <= n
            self.i = self.i % n
        self.n = n
    
    def put(self, x):
        self.i += 1
        if self.i == self.n:
            self.full = True
            self.i %= self.n
        
        if self.full:
            self.x[self.i] = x
        else:
            self.x += [x]
        
    def __iter__(self):
        self.iter_counter = 0
        return self
    def __next__(self):
        i = self.iter_counter
        if i >= len(self.x):
            raise StopIteration
        
        self.iter_counter += 1
        return self.x[i]
        
            

# figure preparation
#fig, ax = plt.subplots(1, 1, figsize = (8, 6))

class Signal:
    def __init__(self, offset = 0, spectrum = [], noise = 0, square = []):
        self.offset = offset
        self.spectrum = spectrum    ## [ [f, A] , ...    ]
        self.square = square        ## [ [f, A, duty], ... ]
        self.noise = noise
    
    def __call__(self, t):
        if type(t) in [list,tuple,np.ndarray]:
            out = np.zeros_like(t, dtype=float)        
            out += self.noise * np.random.randn( len(out) )
        else:
            out = 0
            out += self.noise * np.random.randn()

        for s in self.spectrum:
            out += s[1] * np.sin( 2*PI*s[0]*t )       
        for s in self.square:
            T = 1./s[0]
            tau = t % T
            d = 0.5*T if len(s) < 3 else s[2]*T
            out += s[1] * ( tau < d )    
        
        return out + self.offset
    


class Channel:
    ID_CNT = 0
    colors = ['yellow',  'deepskyblue',  'orangered', 'lawngreen',  'magenta', 'dodgerblue']
    def __init__(self, signal = Signal()):
        self.id = Channel.ID_CNT
        Channel.ID_CNT += 1
        self.name = 'ch'+str(self.id)
        self.signal = signal
        self.active = True
        
        self.voltdiv = 2e-7
        
        self.trig = 0
        self.trig_edge = Trig.Ascending
        
        self.dv = 0
        self.dh = 0
        
        self.invert = False
        
    def color(self):
        return Channel.colors[self.id % len(Channel.colors)]
        
    def __call__(self, t):
        out = self.signal(t)
        if self.invert: out *= -1
        return out

class Oscilloscope:
    ## basic noise due to ele grid
    def __init__(self, noise = Signal(spectrum = [[50,1e-6]], noise = 1e-7)):
        self.noise = Channel(noise)
        self.noise.voltdiv = 3* max( [x[1] for x in noise.spectrum] + [x[1] for x in noise.square] )
        self.channels = {}#ch1.name:ch1}
        self.trig_channel = self.noise
    
        self.samples = Ring(5)
    
        self.hdiv = 12
        self.vdiv = 8
    
        self.secdiv = 5e-3
        #self.voltdiv = 2e-7
        
        self.divsamples = 150
    
        try:
            self.bkg = plt.imread(to_path("lab_meta/OSCI_unit_bkg.png"))
        except:
            self.bkg = None
        
        self.mode = 'TY'   ## for x-y set it a channel list , eg.[ch1, ch2]
        

    def add_channel(self, ch, main = True):
        n = len(self.channels) + 1
        ch.id = n
        ch.name = 'ch'+str(n)
        self.channels[ch.name] = ch
        if main: self.trig_channel = ch
        
        echo = 'added channel '+str(n)
        if main: echo += ' and set it as trigger signal'
        print(echo)
        
    def find_Trig(self, t0 = None, dt = None):
        #print('looking for trig, side is ', edge)
        source = self.trig_channel
        val = source.trig
        edge = source.trig_edge

        if t0 is None:
            t0 = time.time()-T0
        if dt is None:
            dt = 10* self.secdiv / self.divsamples
            
        t = t0
        x = source(t) + self.noise(t)
        
        
        LIM = t+10    ## 10 sec max search
        while(t < LIM):
            t += dt
            y = source(t) + self.noise(t)
            if edge == Trig.Ascending and y > val and x < val:
                return t
            elif edge == Trig.Descending and y < val and x > val:
                return t
            
            x = y
        return -1

    def sample(self):
        trig_time = self.find_Trig( )
        if trig_time < 0:
            print('trig time not found')
            return
        t = np.linspace( trig_time - self.secdiv * self.hdiv/2 , 
                        trig_time + self.secdiv * self.hdiv/2,
                        self.hdiv * self.divsamples )
        
        noise = self.noise(t)
        
        scans = {}
        for chname in self.channels:
            ch = self.channels[chname]
            if ch.active:
                x = ch(t)
                scans[ch.name] = (x + noise) 
        self.samples.put( [t - trig_time,scans] )
        # plot and set axes limits
        
    def init_fig(self):
        fig, ax = self.new_fig()
        self.fig = fig; self.ax = ax
        self.set_fig(self.fig, self.ax)        
    
        
    def set_fig(self, fig , ax ):
        #self.ax.margins(0,0)
        fig.subplots_adjust(left=0, bottom=0,right=1,top=1,wspace=0,hspace=0)
        ax.tick_params(left=False,
                bottom=False,
                labelleft=False,
                labelbottom=False)
        ax.set_facecolor('black')
        
        if self.bkg is None:
            self.plotax = ax
        else:
            ax.imshow(self.bkg, extent = [0 , 1200 , 0, 542 ], zorder = 1)
        
            menuax = fig.add_axes( [ 180/1200 , 72/542 , (670-180)/1200 , (121-72)/542  ] , label = 'menu')
            menuax.set_facecolor('firebrick')
            menuax.tick_params(left=False,
						bottom=False,
						labelleft=False,
						labelbottom=False)       
        
            self.menuax = menuax
            self.plotax = fig.add_axes( [ 180/1200 , 121/542 , (670-180)/1200 , (445-121)/542  ] , label = 'plot')
        
            ax = self.menuax
            ax.cla()
            ax.set_facecolor('firebrick')
        
            cnt = 0
            for chname in self.channels:
                ch = self.channels[chname]
                if ch.active:
                    text = chname + ': {:3g} V/d '.format(ch.voltdiv)+ ' | '
                    ax.text( cnt*0.25 , 0.6, text , zorder = 2, fontsize = 11, color = ch.color())
                    ax.text(cnt*0.25+0.05, 0.1, '({:2g},{:2g})'.format(ch.dh,ch.dv), zorder = 2, fontsize = 10, color = 'white')
                    cnt += 1
			
            text2 = '| dT: {:.2g} s/d'.format(self.secdiv)
            ax.text(0.75,0.4, text2, zorder = 2, fontsize = 11)

        
    def step(self, n = -1):
        if n < 0: n = self.samples.n
        for i in range(n):
            self.sample()
        
    def clear(self):
        self.samples = Ring(5)

    def animation(self, frame = 0):
        self.step(1)
    
        ax = self.plotax
        ax.cla()
    
        ax.set_facecolor('black')

        ax.tick_params(left=False,
                    bottom=False,
                    labelleft=False,
                    labelbottom=False)

        t_base = None      
        
        
        if type(self.mode) is list:
            ch = self.mode
            
            for a in self.samples:
                t, xs = a
                for chname in xs:
                    if chname == ch[0].name:
                        x = xs[chname]
                    if chname == ch[1].name:
                        y = xs[chname]
                
                ax.plot( x/ch[0].voltdiv, y/ch[1].voltdiv , color = ch[0].color())

                
            ax.set_xlim( [ -self.hdiv / 2 , self.hdiv / 2] )
            ax.set_ylim( [ -self.vdiv / 2 , self.vdiv / 2] )
            
            ax.set_xticks( [ - self.hdiv / 2 + i for i in range(self.hdiv) ] )
            ax.set_yticks( [ - self.vdiv / 2 + i for i in range(self.vdiv) ] )           
        else:
            for a in self.samples:
                t, xs = a
                if t_base is None:
                    t_base = t
                for chname in xs:
                    x = xs[chname]
                    ch = self.channels[chname]
                    ax.plot(t + ch.dh, (x + ch.dv) / ch.voltdiv , color = ch.color() , lw = 1)
                
            trig_y = (self.trig_channel.trig + self.trig_channel.dv) / self.trig_channel.voltdiv
            ax.axhline(trig_y, 0,1 , linestyle='-.', color = self.trig_channel.color())
            ax.scatter([t_base[0]],[trig_y], marker = '>', s = 150, color = self.noise.color())
            
                
            ax.set_xlim( [ t_base[0] , t_base[-1]] )
            ax.set_ylim( [ -self.vdiv / 2 , self.vdiv / 2] )
            
            ax.set_xticks( [ t_base[0] + i*self.secdiv for i in range(self.hdiv) ] )
            ax.set_yticks( [ - self.vdiv / 2 + i for i in range(self.vdiv) ] )
         

        
        ax.grid(True, color = self.noise.color(), alpha=0.8, linestyle=':')
        ax.axhline(0, 0,1, lw = 1, color = self.noise.color(), zorder = 2)
        ax.axvline(0, 0,1, lw=1, color = self.noise.color(), zorder = 2)
        
    def new_fig(self):    
        if self.bkg is None:
            fig, ax = plt.subplots(1, 1, figsize = (12, 9))   ## 1:1 aspect
        else:
            fig, ax = plt.subplots(1, 1, figsize = (12, 4.1))
        
        return fig,ax
            
    def show(self):
        fig, ax = self.new_fig()
        self.set_fig(fig,ax)
        self.animation()
        plt.show(block=False)
    
    def screen(self):
        fig, ax = plt.subplots(1, 1, figsize = (12, 9))
        self.plotax = ax
        self.animation()
        plt.show(block=False)
            
    
    def prompt(self):
        line = input()
        while(not line in ['exit','quit']):
            print(line)
            line = input()        
    
    def run(self):
        self.init_fig()
        anim = mani.FuncAnimation(self.fig, self.animation, interval = 250)
        plt.show(block = False)
        self.prompt()

if __name__=='__main__':
    osci = Oscilloscope()
    #osci.trig_edge=Trig.Descending
    #osci.trig = 3e-7
    
    osci.init_fig()
    osci.animation(0)
    plt.show(block=False)
        
    
    ch1 = Channel(Signal(spectrum = [[15,2],[30,3.5],[45,1.5]],noise = 1e-4))
    ch1.voltdiv = 2
    ch1.trig = 3
    
    ch2 = Channel( Signal(spectrum = [[50,2.5]], noise = 1e-4) )
    ch2.voltdiv = 1
    
    osci.add_channel( ch1 )
    osci.add_channel( ch2 , main = False)
    osci.show()
    
    #osci.run()
    

    pass
