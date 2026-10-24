#!/usr/bin/env python3
"""Render aggregate-only scientific figures after all native jobs have ended.

No fitting, interpolation, CDF, motion loading or runtime inference is used.
Matplotlib is imported only inside main, after bounded input validation.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import platform

SOURCES=('mixed','pedestrians')
CONTRACTS=('original','spatial20')
POLICIES=('control','local400')
WINDOWS=(400,1000,2000,4000)
STRATEGY_METHODS=('adaptive_immediate','adaptive_spatial_first','adaptive_temporal_first')
TEMPORAL_METHODS=('adaptive_semantic_first','adaptive_spatial_first','adaptive_temporal_first',
    *(f'fixed_{side}m_{window}ms' for side in (10,20) for window in WINDOWS),
    'static_regional_10m','static_regional_20m')
MAX_JSON_BYTES=32*1024*1024
SOURCE_LABELS={'mixed':'Mixed road users','pedestrians':'Pedestrians only'}
STRATEGY_LABELS={'adaptive_immediate':'Semantic First','adaptive_semantic_first':'Semantic First',
    'adaptive_spatial_first':'Spatial First','adaptive_temporal_first':'Temporal First'}
GRID_COLORS={5:'#0072B2',10:'#D55E00',20:'#009E73'}
WINDOW_MARKERS={400:'o',1000:'^',2000:'s',4000:'D'}
ADAPTIVE_STYLE={'adaptive_immediate':('#882255','P'),
    'adaptive_spatial_first':('#111111','X'),'adaptive_temporal_first':('#332288','*')}
POLICY_COLORS={'control':'#0072B2','local400':'#E69F00'}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def load(path):
    path=Path(path).resolve(strict=True)
    require(path.is_file() and path.stat().st_size<=MAX_JSON_BYTES,'Require a bounded aggregate JSON input')
    raw=path.read_bytes();return json.loads(raw),dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def number(value,label,minimum=None,maximum=None):
    require(type(value) in (int,float) and math.isfinite(value),'Nonfinite/non-numeric '+label)
    require(minimum is None or value>=minimum,'Below range '+label)
    require(maximum is None or value<=maximum,'Above range '+label)
    return value


def checked_metrics(metrics,label,*,compact=False):
    n=number(metrics.get('input_observations' if compact else 'input_observation_contributions'),label+' input',1)
    retained=number(metrics['retained_fraction'],label+' retention',0,1)
    objective=number(metrics['full_input_semantic_distortion'],label+' full-input J',0,1)
    conditional=metrics.get('retained_only_semantic_loss' if compact else 'observation_weighted_semantic_loss')
    if retained:
        number(conditional,label+' conditional semantic loss',0,1)
        expected=1-retained+retained*conditional
    else:
        require(conditional is None,label+': zero retention requires undefined conditional loss')
        expected=1
    require(math.isclose(objective,expected,rel_tol=1e-12,abs_tol=1e-12),label+': J denominator/formula differs')
    return dict(input_observations=n,retained_fraction=retained,full_input_semantic_distortion=objective,
        retained_semantic_loss=conditional)


def strategy_rows(summary):
    require(summary.get('schema')=='ump.strategy-window-extension.v1' and summary.get('status')=='verified'
        and summary.get('completion_scope')=='all_28_predeclared_cases'
        and summary.get('executed_case_count')==summary.get('planned_case_count')==28,
        'Require the completed 28-case strategy/window extension summary')
    expected={(source,contract,method) for source in SOURCES for contract in CONTRACTS for method in
        (*STRATEGY_METHODS,*(f'fixed_{side}m_{window}ms' for side in (5,10,20) for window in WINDOWS))}
    rows=[];seen=set()
    for row in summary['comparison_rows']:
        key=(row['source'],row['contract'],row['method'])
        require(key in expected and key not in seen,'Unexpected/duplicate strategy comparison row: '+str(key));seen.add(key)
        # The strategy runner exposes a compact per-row vocabulary, which differs
        # only in its conditional-loss name from the general compact report.
        adapted=dict(row,retained_only_semantic_loss=row['retained_semantic_loss'])
        rows.append(dict(source=row['source'],contract=row['contract'],method=row['method'],role=row['role'],
            **checked_metrics(adapted,' / '.join(key),compact=True)))
    require(seen==expected,'Strategy matrix is incomplete')
    return rows


def temporal_rows(summary):
    schema=summary.get('schema')
    require(summary.get('completion_scope')=='all_44_predeclared_cases'
        and summary.get('executed_case_count')==summary.get('planned_case_count')==44,
        'Require the full 44-case temporal-region matrix')
    rows=[]
    if schema=='ump.temporal-region-study.v1':
        require(summary.get('status')=='verified','Temporal study is unverified')
        for key,case in summary['cases'].items():
            checked=case.get('independent_audit',{})
            require(checked.get('status')=='verified' and checked.get('scalar_valid') is True
                and checked.get('published_policy_violations')==0,'Unverified temporal case: '+key)
            rows.append(dict(source=case['source'],policy=case['policy'],method=case['method'],
                **checked_metrics(case['stats'],key)))
    elif schema=='ump.temporal-region-aggregate-report.v1':
        require(summary.get('status')=='verified_aggregate_consistency','Temporal aggregate is unverified')
        for case in summary['cases']:
            rows.append(dict(source=case['source'],policy=case['policy'],method=case['method'],
                **checked_metrics(case['metrics'],case['method'],compact=True)))
    else:raise ValueError('Unsupported temporal aggregate schema')
    expected={(source,policy,method) for source in SOURCES for policy in POLICIES for method in TEMPORAL_METHODS[:-2]}
    keys=[(r['source'],r['policy'],r['method']) for r in rows]
    require(len(keys)==len(set(keys)) and set(keys)==expected,'Temporal methods are incomplete/duplicated')
    return rows


def static_rows(summary):
    require(summary.get('schema')=='ump.static-regional-schedule.v1' and summary.get('status')=='verified'
        and summary.get('executed_case_count')==8,'Require all eight verified derived static cases')
    rows=[]
    for key,case in summary['cases'].items():
        checked=case.get('independent_composition_audit',{})
        require(checked.get('status')=='verified' and checked.get('published_policy_violations')==0
            and checked.get('source_assigned_once') is True,'Unverified derived static case: '+key)
        if case['policy']=='control':
            require(checked.get('positive_control_equal_native_4s') is True,'Static positive control equality failed')
        require(case.get('native_runtime') is None and case.get('native_process_wall_seconds') is None
            and case['stats'].get('core_processing_ms') is None,'Derived utility must not fabricate native runtime')
        rows.append(dict(source=case['source'],policy=case['policy'],method=case['method'],
            evidence='Derived utility only; no online runtime',**checked_metrics(case['stats'],key)))
    keys=[(r['source'],r['policy'],r['method']) for r in rows]
    expected={(source,policy,method) for source in SOURCES for policy in POLICIES for method in TEMPORAL_METHODS[-2:]}
    require(len(keys)==len(set(keys)) and set(keys)==expected,'Derived static matrix is incomplete/duplicated')
    return rows


def fixed_parts(method):
    pieces=method.split('_');require(len(pieces)==3 and pieces[0]=='fixed','Invalid fixed method')
    side=int(pieces[1][:-1]);window=int(pieces[2][:-2]);return side,window


def label(method):
    if method in STRATEGY_LABELS:return STRATEGY_LABELS[method]
    if method.startswith('static_regional_'):return 'Static regional '+method.rsplit('_',1)[1]+' [derived]'
    side,window=fixed_parts(method)
    return f'Fixed {side} m / {window/1000:g} s'


def save(fig,output,stem,plt):
    paths=[]
    for suffix,kwargs in (('png',dict(dpi=240)),('svg',{})):
        path=output/(stem+'.'+suffix)
        fig.savefig(path,facecolor='white',bbox_inches='tight',metadata={'Description':
            'Exact aggregate outcomes. One frozen realization per source. No fitted model; no attack-based privacy claim.'},**kwargs)
        if suffix == 'svg':
            # Keep generated vector assets clean in source-control checks.
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
        paths.append(path)
    plt.close(fig)
    return paths


def plot_strategy(rows,output,plt,Line2D):
    fig,axes=plt.subplots(2,2,figsize=(16.8,12.0),sharex=True,sharey=True)
    for source_index,source in enumerate(SOURCES):
        for contract_index,contract in enumerate(CONTRACTS):
            ax=axes[source_index,contract_index]
            selected=[row for row in rows if row['source']==source and row['contract']==contract]
            fixed=[row for row in selected if row['method'].startswith('fixed_')]
            # Every coordinate is the exact outcome; coincident results are
            # neither jittered nor separated into artificial pseudo-observations.
            for row in fixed:
                side,window=fixed_parts(row['method'])
                ax.scatter(row['retained_fraction']*100,row['full_input_semantic_distortion']*100,
                    marker=WINDOW_MARKERS[window],s=44+WINDOWS.index(window)*13,facecolors='none',
                    edgecolors=GRID_COLORS[side],linewidths=1.4,zorder=3)
            for order,method in enumerate(STRATEGY_METHODS):
                row=next(row for row in selected if row['method']==method);color,marker=ADAPTIVE_STYLE[method]
                x,y=row['retained_fraction']*100,row['full_input_semantic_distortion']*100
                ax.scatter(x,y,marker=marker,s=165 if marker=='*' else 110,c=color,
                    edgecolors='white',linewidths=.65,zorder=5)
                offsets=((10,16),(10,-17),(10,0))
                ax.annotate(STRATEGY_LABELS[method],(x,y),xytext=offsets[order],textcoords='offset points',
                    fontsize=9,color=color,ha='left',va='center',
                    arrowprops=dict(arrowstyle='-',lw=.65,color=color),zorder=6)
            coincidences=defaultdict(list)
            for row in fixed:
                coincidences[(round(row['retained_fraction'],12),round(row['full_input_semantic_distortion'],12))].append(row['method'])
            for (retention,objective),methods in coincidences.items():
                if len(methods)>1 and retention==0 and objective==1:
                    ax.annotate(f'{len(methods)} fixed configurations\nzero release\n(policy rejection)',
                        xy=(0,100),xytext=(8,68),textcoords='data',fontsize=9,color='#555555',
                        arrowprops=dict(arrowstyle='-',lw=.6,color='#888888'),ha='left',va='top')
            ax.set_title(SOURCE_LABELS[source]+' / '+('Original policy' if contract=='original' else 'Spatial20 policy'),fontsize=12,pad=10)
            ax.set_xlim(-3,103);ax.set_ylim(-3,104);ax.set_xticks(range(0,101,20));ax.set_yticks(range(0,101,20))
            ax.grid(color='#dddddd',linewidth=.6);ax.set_axisbelow(True)
            if source_index==1:ax.set_xlabel('Retained input observations (%) → higher is better',fontsize=11)
            if contract_index==0:ax.set_ylabel('Full-input distortion J (%) → lower is better',fontsize=11)
    handles=[]
    for side,color in GRID_COLORS.items():
        handles.append(Line2D([],[],marker='o',ls='',mfc='none',mec=color,mew=1.5,markersize=8,label=f'Fixed {side} m grid'))
    for window,marker in WINDOW_MARKERS.items():
        handles.append(Line2D([],[],marker=marker,ls='',mfc='none',mec='#555555',markersize=8,label=f'Fixed {window/1000:g} s window'))
    for method,(color,marker) in ADAPTIVE_STYLE.items():
        handles.append(Line2D([],[],marker=marker,ls='',color=color,markersize=10,label=STRATEGY_LABELS[method]))
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.055),ncol=5,frameon=False,fontsize=10,
        columnspacing=1.8,handletextpad=.6)
    fig.suptitle('Strategy and fixed-window comparison on unchanged observation streams',fontsize=16,y=.99)
    fig.text(.5,.016,'Each facet: 12 fixed configurations and 3 adaptive strategies. Selective suppression OFF.\n'
        'J = omitted-input fraction + retained-input fraction × retained taxonomy loss. Exact outcomes; no fitted curves; one realization per source.',
        ha='center',va='bottom',fontsize=9,color='#444444')
    fig.subplots_adjust(left=.09,right=.97,top=.94,bottom=.18,hspace=.24,wspace=.10)
    return save(fig,output,'strategy-retention-distortion',plt)


def plot_temporal(rows,output,metric,plt,Patch):
    require(metric in ('retained_fraction','full_input_semantic_distortion'),'Unexpected primary objective')
    objective=metric=='full_input_semantic_distortion'
    title='Full-input distortion under a local freshness constraint' if objective else 'Retention under a local freshness constraint'
    axis_label='Full-input distortion J (%) — lower is better' if objective else 'Retained input observations (%) — higher is better'
    fig,axes=plt.subplots(1,2,figsize=(17.2,11.2),sharey=True,sharex=True)
    index={(row['source'],row['policy'],row['method']):row for row in rows}
    for source,ax in zip(SOURCES,axes):
        ax.axhspan(-.5,2.5,color='#f2eef7',zorder=0)
        ax.axhspan(10.5,12.5,color='#eef4f7',zorder=0)
        for position,method in enumerate(TEMPORAL_METHODS):
            derived=method.startswith('static_regional_')
            for policy,offset in (('control',-.18),('local400',.18)):
                value=index[(source,policy,method)][metric]*100
                ax.barh(position+offset,value,height=.32,color=POLICY_COLORS[policy],
                    edgecolor='#555555' if derived else 'white',linewidth=.5,
                    hatch='///' if derived else None,zorder=3)
                ax.text(value+.7,position+offset,f'{value:.1f}',ha='left',va='center',fontsize=9,
                    color='#333333',zorder=4)
        for separator in (2.5,10.5):ax.axhline(separator,color='#aaaaaa',lw=.6,ls='--',zorder=1)
        ax.set_title(SOURCE_LABELS[source],fontsize=13,pad=12)
        ax.set_xlim(0,108);ax.set_xticks(range(0,101,20));ax.set_xlabel(axis_label,fontsize=11,labelpad=10)
        ax.set_yticks(range(len(TEMPORAL_METHODS)));ax.set_yticklabels([label(method) for method in TEMPORAL_METHODS],fontsize=10)
        ax.grid(axis='x',color='#dddddd',lw=.6,zorder=0);ax.set_axisbelow(True)
        ax.tick_params(axis='y',length=0,pad=8)
    axes[0].invert_yaxis()
    handles=[Patch(facecolor=POLICY_COLORS['control'],label='Control: temporal limit 4 s everywhere'),
        Patch(facecolor=POLICY_COLORS['local400'],label='Treatment: central-region window/age ≤ 0.4 s'),
        Patch(facecolor='white',edgecolor='#555555',hatch='///',label='Derived static regional schedule; utility only')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.075),ncol=1,frameon=False,fontsize=10)
    fig.suptitle(title,fontsize=16,y=.98)
    fig.text(.5,.019,'Same input observations and hard policy for every method within each policy condition; suppression OFF.\n'
        'Static regional windows are chosen from public constraints before observation processing. No native runtime is inferred for derived results.\n'
        'One realization per source; operational policy compliance and utility are evaluated. No empirical or formal privacy gain is claimed.',
        ha='center',va='bottom',fontsize=9,color='#444444')
    fig.subplots_adjust(left=.21,right=.98,top=.92,bottom=.21,wspace=.12)
    stem='temporal-region-full-input-loss' if objective else 'temporal-region-retention'
    return save(fig,output,stem,plt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy-summary',required=True,type=Path)
    parser.add_argument('--temporal-summary',required=True,type=Path,
        help='Completed native study summary or its verified aggregate-report.json')
    parser.add_argument('--static-summary',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path,help='Fresh figure directory; never overwritten')
    args=parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(),'Choose a fresh figure output directory')
    strategy,strategy_receipt=load(args.strategy_summary)
    temporal,temporal_receipt=load(args.temporal_summary)
    static,static_receipt=load(args.static_summary)
    first=strategy_rows(strategy);native=temporal_rows(temporal);derived=static_rows(static)
    denominators=defaultdict(set)
    for row in (*first,*native,*derived):denominators[row['source']].add(row['input_observations'])
    require(all(len(values)==1 for values in denominators.values()),'Source denominators differ between figures/studies')
    # Import and render only when the operator explicitly invokes this script
    # after native benchmarks have ended. No module-level plotting side effects.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    matplotlib.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False,'savefig.pad_inches':.12})
    args.output.mkdir(parents=True,mode=0o700)
    outputs=plot_strategy(first,args.output,plt,Line2D)
    outputs+=plot_temporal([*native,*derived],args.output,'retained_fraction',plt,Patch)
    outputs+=plot_temporal([*native,*derived],args.output,'full_input_semantic_distortion',plt,Patch)
    exact=args.output/'figure-data.json'
    exact.write_text(json.dumps(dict(schema='ump.e25-scientific-figure-data.v1',
        strategy_comparison=first,temporal_native=native,static_derived=derived),indent=2,sort_keys=True,allow_nan=False)+'\n')
    outputs.append(exact)
    inputs=dict(strategy_summary=strategy_receipt,temporal_summary=temporal_receipt,static_summary=static_receipt)
    for receipt in inputs.values():
        require(sha(receipt['path'])==receipt['sha256'],'Input summary changed during plotting')
    receipt=dict(schema='ump.e25-scientific-figure-receipt.v1',inputs=inputs,
        plotting_script=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__))),
        environment=dict(python=platform.python_version(),matplotlib=matplotlib.__version__),
        outputs={path.name:dict(bytes=path.stat().st_size,sha256=sha(path)) for path in outputs},
        scope='Exact aggregate outcomes; no fitting, interpolation, CDF or generated measurements. Derived static results carry no runtime claim. One frozen realization per source.',
        objective='J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input; unit omission cost. Experimental utility, not privacy risk.')
    (args.output/'figure-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(dict(status='rendered',figures=3,formats=['png','svg'],output=str(args.output))))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError) as error:raise SystemExit('Scientific figure generation failed: '+str(error))
