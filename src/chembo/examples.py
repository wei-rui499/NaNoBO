"""Small explicitly simulated examples for learning each workflow."""
from chembo.app import example_project


def workflow_example(mode):
    p = example_project()
    p.update(engine='bo-mcp', task='optimization', objective_mode='hierarchical')
    if mode == 'recipe':
        p.update(name='教学示例 · 总量与步长', parameters=[dict(name='A',type='continuous',low=0,high=1,step=.1,unit='mL'),dict(name='B',type='continuous',low=0,high=1,step=.1,unit='mL')], constraints=[dict(kind='linear',coefficients={'A':1,'B':1},relation='eq',rhs=1)], observations=[dict(A=.1,B=.9,response=.3),dict(A=.3,B=.7,response=.7),dict(A=.5,B=.5,response=.9),dict(A=.7,B=.3,response=.6)])
    elif mode == 'pareto':
        p.update(name='教学示例 · 性能与成本', objective_mode='pareto', objectives=[dict(name='performance',goal='max',tolerance=.2),dict(name='cost',goal='min',tolerance=.2)])
        for i, row in enumerate(p['observations']):
            row['performance'] = row.pop('response')
            row['cost'] = [.15,.55,.7,.9,.3][i]
    elif mode == 'classification':
        p.update(name='教学示例 · 成功与失败', task='classification', classification={'labels':['成功','失败']}, objectives=[dict(name='outcome',goal='max',tolerance=.2)])
        for i, row in enumerate(p['observations']):
            row.pop('response')
            row['outcome'] = ['失败','成功','失败','成功','失败'][i]
    return p
