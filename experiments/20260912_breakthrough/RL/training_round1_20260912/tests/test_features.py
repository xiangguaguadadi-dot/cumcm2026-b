"""Pure public event feature tests, without world/backend construction."""
from copy import deepcopy
import unittest
from ..features import event_projection,active_history,validate_features,validate_snapshot

def event(index,action,time_s,delta_s,channel=1,kind='direction',bearing=0.,position=(0.,0.)):
    request={} if action in ('enter','exit') else {'channel':channel,'position':dict(zip(('x','y'),position))}
    response=dict(accepted=True,virtual_time_s=time_s,real_timestamp_ms=1234)
    if action=='measure':response['measure_result']=kind
    if kind=='direction' and action=='measure':response['svd_deg']=bearing
    if action=='clear':response['clear_result']=kind
    return dict(index=index,action=action,request=request,response=response,delta_time_s=delta_s,
                backend_call_s=987.,compute_since_previous_response_s=456.)

class FeatureTests(unittest.TestCase):
    def test_machine_clocks_do_not_enter_projection(self):
        a=[event(0,'enter',0.,0.),event(1,'measure',5.,5.)];b=deepcopy(a)
        b[1]['response']['real_timestamp_ms']=999;b[1]['backend_call_s']=1e10
        self.assertEqual(event_projection(a),event_projection(b))
        self.assertFalse(any('real' in k or 'backend' in k for e in event_projection(a)[0] for k in e))

    def test_event_delta_not_active_channel_gap(self):
        events=[event(0,'enter',0,0),event(1,'measure',5,5),event(2,'measure',105,100,channel=2),
                event(3,'measure',111,6,kind='no_signal')]
        projected,end=event_projection(events)
        values,dropped=active_history(projected,channel=1,position=(0,0),theta_deg=0,snapshot_us=end)
        self.assertEqual(len(values),2);self.assertEqual(dropped,0)
        self.assertAlmostEqual(values[1][12],6/2300)
        self.assertAlmostEqual(values[0][10],106/10000)
        self.assertEqual(values[1][11],1.)

    def test_history_keeps_first_positive_and_recent127(self):
        events=[event(0,'enter',0,0)]+[event(i,'measure',5*i,5,kind='direction' if i==1 else 'no_signal') for i in range(1,201)]
        projected,end=event_projection(events)
        values,dropped=active_history(projected,channel=1,position=(0,0),theta_deg=0,snapshot_us=end)
        self.assertEqual((len(values),dropped),(128,72));self.assertEqual(values[0][13],1.)
        self.assertEqual(values[-1][10],0.)

    def test_missing_positive_or_future_event_rejected(self):
        projected,end=event_projection([event(0,'enter',0,0),event(1,'measure',5,5,kind='no_signal')])
        with self.assertRaises(ValueError):active_history(projected,channel=1,position=(0,0),theta_deg=0,snapshot_us=end)
        projected,end=event_projection([event(0,'enter',0,0),event(1,'measure',5,5)])
        with self.assertRaises(ValueError):active_history(projected,channel=1,position=(0,0),theta_deg=0,snapshot_us=end-1)

    def test_unknown_hidden_field_and_broken_ledger_rejected(self):
        a=[event(0,'enter',0,0),event(1,'measure',5,5)]
        b=deepcopy(a);b[1]['response']['true_n']=10
        with self.assertRaises(ValueError):event_projection(b)
        b=deepcopy(a);b[1]['delta_time_s']=4
        with self.assertRaises(ValueError):event_projection(b)
        b=deepcopy(a);b[1]['index']=2
        with self.assertRaises(ValueError):event_projection(b)

    def test_near_and_clear_outcomes_distinct(self):
        rows=[event(0,'enter',0,0),event(1,'measure',5,5),event(2,'measure',10,5,kind='near'),
              event(3,'clear',15,5,kind='success'),event(4,'clear',18,3,kind='no_target_in_range')]
        projected,end=event_projection(rows)
        values,_=active_history(projected,channel=1,position=(0,0),theta_deg=0,snapshot_us=end)
        self.assertEqual([v[:5] for v in values],[[1.,0.,0.,0.,0.],[0.,1.,0.,0.,0.],[0.,0.,0.,0.,1.],[0.,0.,0.,1.,0.]])

if __name__=='__main__':unittest.main()
