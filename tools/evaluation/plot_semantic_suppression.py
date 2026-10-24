#!/usr/bin/env python3
"""Plot compact verified suppression-study aggregates, never raw motion data."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

METHODS=(('semantic_first','Semantic First\n≤4 s'),
         ('spatial_first','Spatial First\n≤4 s'),
         ('fixed_10m_1000ms','Fixed 10 m\n1 s'))
PANELS=(('retained_fraction','Retained input','Full input retained (%)'),
        ('conditional_semantic_loss','Semantic loss among retained','Retained-contribution denominator (%)'),
        ('full_input_semantic_distortion','Full-input semantic distortion','Full-input denominator; unit omission cost (%)'))


def plot(summary_path,output_prefix):
    summary_path,output_prefix=Path(summary_path),Path(output_prefix)
    if not summary_path.is_file() or summary_path.stat().st_size>2*1024**2:
        raise ValueError('Require compact JSON evidence of at most 2 MiB')
    summary=json.loads(summary_path.read_text())
    if summary.get('schema')!='ump.selective-semantic-study.v1' or summary.get('status')!='verified':
        raise ValueError('Require verified selective semantic study evidence')
    expected={name+'_'+flag for name,_ in METHODS for flag in ('off','on')}
    if set(summary.get('cases',{}))!=expected:
        raise ValueError('Require the complete six-case comparison')
    for name,case in summary['cases'].items():
        audit=case.get('independent_audit',{})
        if audit.get('status')!='verified' or audit.get('raw_ownership_valid') is not True or audit.get('published_policy_violations')!=0:
            raise ValueError('Require independent zero-violation audit: '+name)
        for metric,_,_ in PANELS:
            value=case[metric]
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
                raise ValueError('Invalid metric: '+name+'/'+metric)
    paths=[output_prefix.with_suffix(suffix) for suffix in ('.png','.svg')]
    if any(path.exists() for path in paths): raise ValueError('Choose a fresh output prefix')
    output_prefix.parent.mkdir(parents=True,exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'ump-semantic-suppression-2026-10-24'})
    fig,axes=plt.subplots(1,3,figsize=(12.5,5.1))
    colors=('#2A5674','#C56B27');width=.34
    for ax,(metric,title,ylabel) in zip(axes,PANELS):
        ax.set_axisbelow(True);ax.grid(axis='y',color='#E0E5E8',linewidth=.65)
        for flag,offset,color in (('off',-width/2,colors[0]),('on',width/2,colors[1])):
            values=[100*summary['cases'][name+'_'+flag][metric] for name,_ in METHODS]
            bars=ax.bar([i+offset for i in range(3)],values,width,color=color,zorder=3)
            for bar,value in zip(bars,values):
                ax.text(bar.get_x()+bar.get_width()/2,value+1.2,f'{value:.2f}',ha='center',va='bottom',fontsize=8.5)
        ax.set_xticks(range(3),[label for _,label in METHODS],fontsize=9)
        ax.set_ylim(0,100);ax.set_yticks(range(0,101,20))
        ax.set_title(title,fontsize=11,pad=10,fontweight='semibold')
        ax.set_ylabel(ylabel,fontsize=9)
    fig.suptitle('Policy-controlled contribution suppression · one recorded source',fontsize=15,x=.04,ha='left',y=.98)
    first=summary['cases']['semantic_first_off'];n=first['input_observations']
    fig.text(.04,.905,f"Post-hoc 60 s prefix · {n:,} observation contributions · same taxonomy and regional hard constraints",fontsize=10,color='#37474F')
    fig.legend(handles=[Patch(facecolor=colors[0],label='Suppression off'),Patch(facecolor=colors[1],label='Suppression on: cell-window cap 10%')],
        loc='upper left',bbox_to_anchor=(.035,.875),ncol=2,frameon=False,fontsize=10)
    fig.subplots_adjust(left=.055,right=.985,bottom=.29,top=.72,wspace=.29)
    fig.text(.04,.105,'Full-input distortion = (all omitted contributions + retained taxonomy cost) / original input.',fontsize=9,color='#37474F')
    fig.text(.04,.066,'Adaptive methods may use 4 s; fixed comparator chooses 1 s. This is a limited portfolio, not the best fixed schedule.',fontsize=9,color='#37474F')
    fig.text(.04,.027,'Declared utility/support measures; no measured privacy gain or real-time guarantee.  Source prefix SHA-256: '+summary['protocol']['derived_input_sha256'][:12],fontsize=8.5,color='#546E7A')
    fig.savefig(paths[0],dpi=170,metadata={'Software':'UMP-Simulator / plot_semantic_suppression.py'})
    fig.savefig(paths[1],metadata={'Title':'Policy-controlled contribution suppression','Creator':'UMP-Simulator / plot_semantic_suppression.py','Date':'2026-10-24'})
    plt.close(fig)
    return paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True);parser.add_argument('--output-prefix',type=Path,required=True)
    args=parser.parse_args()
    for path in plot(args.summary,args.output_prefix):print(path)


if __name__=='__main__':main()
