#!/usr/bin/env python3
"""Export a static scientific summary of predeclared private study reports.

Matplotlib is optional and required only by this export tool, not by evaluation.
The plot shows empirical attack ranking and answered-query coverage separately.
"""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports',type=Path,nargs='+',required=True)
    parser.add_argument('--labels',nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True,help='New output prefix; writes PNG and SVG')
    args=parser.parse_args()
    if len(args.reports)!=len(args.labels):
        parser.error('One label is required per report')
    destinations=[args.output.with_suffix(suffix) for suffix in ('.png','.svg')]
    if any(p.exists() or p.is_symlink() for p in destinations):
        parser.error('Output files already exist')
    reports=[json.loads(path.read_text()) for path in args.reports]
    if any(r.get('schema')!='ump.empirical-privacy-report.v1' or r.get('status')!='complete' for r in reports):
        parser.error('Only complete empirical study reports are accepted')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    methods=['fixed_10m_400ms','fixed_10m_1000ms','fixed_20m_400ms','fixed_20m_1000ms',
             'spatial','temporal_first','spatial_first']
    names=['Fixed 10 m / 400 ms','Fixed 10 m / 1000 ms','Fixed 20 m / 400 ms',
           'Fixed 20 m / 1000 ms','Spatial only','Temporal First (space first)',
           'Spatial First (time first)']
    colors=['#2463a2','#b85e20','#43805d','#865db2']
    figure,axes=plt.subplots(1,2,figsize=(12,6.5),sharey=True,layout='constrained')
    for series,(report,label) in enumerate(zip(reports,args.labels)):
        offset=(series-(len(reports)-1)/2)*.21
        selected={a['variant']:a for a in report['attacks']
                  if a['knowledge_fraction']==1 and a['feature_set']=='counts_geometry_time'}
        for index,method in enumerate(methods):
            attack=selected[method]
            auc=attack['test']['roc_auc']
            low,high=attack['test_uncertainty']['intervals']['roc_auc']
            axes[0].errorbar(auc,index+offset,xerr=[[auc-low],[high-auc]],fmt='o',
                ms=5,capsize=3,color=colors[series%len(colors)],label=label if index==0 else None)
            axes[1].plot(100*report['utility'][method]['answered_query_coverage'],index+offset,
                'o',ms=5,color=colors[series%len(colors)])
    axes[0].axvline(.5,color='#777777',linestyle='--',linewidth=1)
    axes[0].set_xlim(.38,.85)
    axes[0].set_xlabel('Held-out membership ROC-AUC (95% conditional bootstrap interval)')
    axes[0].set_title('Evaluated attack performance')
    axes[1].set_xlim(0,25)
    axes[1].set_xlabel('Answered fixed occupancy queries (%)')
    axes[1].set_title('Availability on the unchanged 10 m / 1 s query')
    axes[0].set_yticks(range(len(names)),names)
    axes[0].invert_yaxis()
    for axis in axes:
        axis.grid(axis='x',alpha=.2)
        axis.spines[['top','right']].set_visible(False)
    handles,labels=axes[0].get_legend_handles_labels()
    axes[1].legend(handles,labels,loc='upper right',fontsize=9)
    figure.suptitle('Controlled synthetic source-membership benchmark',fontsize=15)
    figure.supxlabel('Full candidate trace; 31 public features; 32 paired test groups per configuration.\n'
        'No-output control: AUC 0.5, coverage 0. Model/threshold fixed before test evaluation.',fontsize=10)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for destination in destinations:
        figure.savefig(destination,dpi=180)
        if destination.suffix=='.svg':
            destination.write_text('\n'.join(line.rstrip() for line in destination.read_text().splitlines())+'\n')
    plt.close(figure)
    print('Exported '+', '.join(map(str,destinations)))


if __name__=='__main__':
    main()
