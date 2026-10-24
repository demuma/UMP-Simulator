#!/usr/bin/env python3
"""Plot measured fixed-grid responses, without fitting a regression to three sizes.

Each Policy Tree receives its own figure. Fixed schedules use connected measured
5/10/20-m points. Adaptive strategies are aggregate horizontal references under
that same policy; the plot does not imply their outputs have a uniform cell size.
Only compact audited summaries are read; source movements are never needed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

import run_comparison

MAX_SUMMARY_BYTES=4*1024*1024
SIDES=(5,10,20)
WINDOWS=(400,1000)
ADAPTIVE=(('adaptive_immediate','Semantic First','#52745b',':'),
          ('adaptive_spatial_first','Spatial First','#8f4f79','--'))
METRICS=(('retained_fraction','Retained observation contributions','Full input retained (%)',100),
         ('observation_weighted_semantic_loss','Semantic loss of retained data','Conditional taxonomy loss (%)',100),
         ('full_input_semantic_distortion','Semantic distortion including omissions','Full-input distortion (%)',100),
         ('delay_p95_ms','Observation-to-release delay','Retained-observation p95 (s)',None))


def metric(value,name,maximum=None):
    if value is None:return None
    if type(value) not in (int,float) or not math.isfinite(value) or value<0 or (maximum is not None and value>maximum):
        raise ValueError('Invalid spatial-portfolio metric: '+name)
    return value


def measured_series(summary):
    if summary.get('schema')!='ump.mapped-comparison.v1' or summary.get('status')!='verified':
        raise ValueError('Require a verified compact mapped comparison summary')
    protocol=summary.get('protocol',{})
    if protocol.get('comparison_kind')!='spatial_resolution_portfolio':
        raise ValueError('Require the declared spatial-resolution portfolio')
    profiles=protocol.get('spatial_profiles')
    coverage=dict(width=80,height=80,leaf_depth=6)
    matrix=run_comparison.spatial_portfolio_variants(coverage,profiles)
    expected={row['id'] for row in matrix}
    declared=protocol.get('matrix',[])
    if len(declared)!=len(expected) or {row.get('id') for row in declared}!=expected or set(summary.get('cases',{}))!=expected:
        raise ValueError('Require every case in the complete predeclared spatial portfolio')
    for row in declared:
        method=next(item for item in matrix if item['id']==row['id'])
        if row.get('mode')!=method['mode'] or row.get('suppression_cap')!=0:
            raise ValueError('Spatial portfolio strategy/filtering differs from its declared method')
        if method['mode']=='fixed' and (row.get('side_m')!=method['side_m'] or row.get('window')!=method['window']):
            raise ValueError('Fixed-grid side or window differs from the declared schedule')
    source_n=summary.get('source',{}).get('input_observation_contributions')
    if type(source_n) is not int or source_n<0:raise ValueError('Require a nonnegative full-source denominator')
    values={}
    for name,case in summary['cases'].items():
        audit=case.get('independent_audit',{})
        if audit.get('status')!='verified' or audit.get('scalar_valid') is not True or audit.get('published_policy_violations')!=0:
            raise ValueError('Every plotted case requires an independent zero-violation audit: '+name)
        stats=case['stats']
        if stats.get('input_observation_contributions')!=source_n:
            raise ValueError('All plotted methods must share the same full-source denominator')
        raw={key:stats.get(key) for key,_,_,_ in METRICS}
        raw['delay_p95_ms']=stats.get('source_accounting',{}).get('observation_to_release_delay_ms',{}).get('p95')
        values[name]={key:None if value is None else metric(value,name+' '+key,1 if key!='delay_p95_ms' else None)*(.001 if key=='delay_p95_ms' else 100)
                      for key,value in raw.items()}
    return dict(profiles=list(profiles),cases=values)


def plot(summary_path,output):
    summary_path,output=Path(summary_path).resolve(),Path(output).resolve()
    if not summary_path.is_file() or summary_path.stat().st_size>MAX_SUMMARY_BYTES:
        raise ValueError('Summary must be a regular JSON file of at most 4 MiB')
    if output.exists():raise ValueError('Choose a fresh figure output directory')
    raw=summary_path.read_bytes();summary=json.loads(raw);series=measured_series(summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
                         'axes.spines.top':False,'axes.spines.right':False})
    output.mkdir(parents=True,mode=0o700)
    artifacts=[]
    for profile in series['profiles']:
        fig,axes=plt.subplots(2,2,figsize=(12,8.6))
        colors=('#2A5674','#C56B27')
        for ax,(key,title,ylabel,upper) in zip(axes.flat,METRICS):
            present=[case[key] for name,case in series['cases'].items() if name.startswith(profile+'_') and case[key] is not None]
            ax.set_ylim(0,upper if upper is not None else max(max(present,default=1)*1.2,1))
            for index,window in enumerate(WINDOWS):
                ys=[series['cases'][f'{profile}_fixed_{side}m_{window}ms'][key] for side in SIDES]
                ax.plot(SIDES,[float('nan') if value is None else value for value in ys],marker='o',markersize=6,
                        color=colors[index],linewidth=1.7,zorder=3)
                for side,value in zip(SIDES,ys):
                    if value is None:
                        ax.text(side-.3+index*.6,.035+index*.075,'n/a',transform=ax.get_xaxis_transform(),
                                color=colors[index],fontsize=8,ha='center')
            for method,_,color,style in ADAPTIVE:
                value=series['cases'][profile+'_'+method][key]
                if value is not None:ax.axhline(value,color=color,linestyle=style,linewidth=1.5,zorder=2)
            ax.set_title(title,fontsize=12,pad=12)
            ax.set_ylabel(ylabel);ax.set_xlabel('Requested uniform grid cell side (m)')
            ax.set_xticks(SIDES);ax.set_xlim(4,21)
            ax.grid(color='#E2E5E7',linewidth=.7,zorder=0);ax.set_axisbelow(True)
        fig.suptitle(('Original Policy Tree' if profile=='original' else 'Spatial20 Policy Tree')+' · identical recorded observations',
                     fontsize=16,fontweight='semibold',y=.98)
        subtitle=('20-m releases violate the original spatial limit: deliberate negative controls.' if profile=='original' else
                  'Every root/region cell-side maximum is 20 m for every method; other hard bounds remain.')
        fig.text(.5,.94,subtitle,ha='center',fontsize=10,color='#40464A')
        handles=[Line2D([0],[0],color=color,marker='o',label=f'Fixed grid · {window/1000:g} s') for color,window in zip(colors,WINDOWS)]
        handles += [Line2D([0],[0],color=color,linestyle=style,label=label+' · same-policy reference') for _,label,color,style in ADAPTIVE]
        fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.918),ncol=2,frameon=False,fontsize=9)
        fig.text(.5,.027,'Connected points are measured schedules, not a fitted regression or a prediction between grid sizes.\n'
                 'Adaptive references retain their own variable cell sizes/windows (up to 4 s). Missing conditional metrics are n/a.\n'
                 'Distortion assigns cost 1 to omitted contributions. Policy compliance and utility do not establish measured privacy gain.',
                 ha='center',fontsize=9,color='#40464A',linespacing=1.5)
        fig.subplots_adjust(left=.085,right=.98,top=.82,bottom=.16,wspace=.26,hspace=.5)
        try:
            for suffix in ('png','svg'):
                filename=f'spatial-portfolio-{profile}.{suffix}';artifacts.append(filename)
                kwargs={'dpi':180} if suffix=='png' else {'metadata':{'Date':None}}
                fig.savefig(output/filename,facecolor='white',**kwargs)
                if suffix=='svg':
                    # Matplotlib path strings contain line-end spaces. Normalize
                    # text formatting for clean repository diffs; geometry stays.
                    path=output/filename
                    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
        finally:plt.close(fig)
    metadata=dict(schema='ump.spatial-portfolio-figure.v1',summary_sha256=hashlib.sha256(raw).hexdigest(),
                  artifacts=artifacts,measured_series=series,fixed_grid_sides_m=list(SIDES),fixed_windows_ms=list(WINDOWS),
                  trend_scope='Straight segments only connect measured fixed schedules; no regression, confidence interval, interpolation claim or extrapolation.',
                  adaptive_scope='Horizontal aggregate references under the same Policy Tree; they do not imply uniform adaptive cell size.',
                  missing_value_rule='Missing conditional utility is n/a, never zero; zero retained fraction remains an actual measured zero.')
    with (output/'figure-provenance.json').open('x') as handle:
        json.dump(metadata,handle,indent=2,allow_nan=False);handle.write('\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plot(args.summary,args.output)


if __name__=='__main__':main()
