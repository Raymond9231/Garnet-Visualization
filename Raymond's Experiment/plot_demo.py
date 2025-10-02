import re
import os
import plotly.graph_objects as go
import numpy as np
from collections import defaultdict

# ========== Step 1. Parse processed.txt with flit tracking ==========
def parse_log(filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename=os.path.join(script_dir, filename)
    """
    Parse log and track which flits are currently at each router/link at each tick.
    Strategy: Build complete state at each tick by tracking flit movements.
    """
    # Track current location of each flit (global_id -> location info)
    flit_locations = {}
    
    # Read and parse all events
    events = []
    with open(filename, "r") as f:
        for line in f:
            if not line.startswith("###"):
                continue
            parts = line.strip().split()
            tick = int(parts[1])
            event = parts[2]
            global_id = int(parts[3])
            pack_id = int(parts[4])
            flit_id = int(parts[5])
            
            events.append({
                'tick': tick,
                'event': event,
                'global_id': global_id,
                'pack_id': pack_id,
                'flit_id': flit_id,
                'parts': parts
            })
    
    # Sort by tick
    events.sort(key=lambda x: x['tick'])
    
    # Track state changes
    tick_states = {}  # tick -> state snapshot
    
    for evt in events:
        tick = evt['tick']
        event = evt['event']
        global_id = evt['global_id']
        pack_id = evt['pack_id']
        flit_id = evt['flit_id']
        parts = evt['parts']
        
        # Initialize flit info on first encounter (RI event)
        if event == 'RI':
            src = int(parts[6])
            dest = int(parts[7])
            flit_locations[global_id] = {
                'src': src,
                'dest': dest,
                'pack_id': pack_id,
                'flit_id': flit_id,
                'location_type': None,
                'location_id': None
            }
        
        # Update flit location based on event
        if global_id in flit_locations:
            if event == 'SI':
                # Flit enters router from external link (injection)
                ext_link_id = int(parts[6])
                router_id = ext_link_id
                flit_locations[global_id]['location_type'] = 'router'
                flit_locations[global_id]['location_id'] = router_id
            
            elif event == 'RR':
                # Router receives flit
                router_id = int(parts[6])
                flit_locations[global_id]['location_type'] = 'router'
                flit_locations[global_id]['location_id'] = router_id
            
            elif event == 'ST':
                # Flit starts transmitting on internal link
                int_link_id = int(parts[6])
                flit_locations[global_id]['location_type'] = 'link'
                flit_locations[global_id]['location_id'] = int_link_id
            
            elif event == 'DT':
                # Flit during transmission (still on link)
                int_link_id = int(parts[6])
                flit_locations[global_id]['location_type'] = 'link'
                flit_locations[global_id]['location_id'] = int_link_id
            
            elif event == 'SE':
                # Flit ejects (leaves the network)
                flit_locations[global_id]['location_type'] = 'ejected'
                flit_locations[global_id]['location_id'] = None
        
        # Save state snapshot at this tick
        # Create snapshot of ALL active flits at this moment
        snapshot = {'routers': defaultdict(list), 'links': defaultdict(list)}
        
        for gid, loc in flit_locations.items():
            if loc['location_type'] == 'router' and loc['location_id'] is not None:
                router_id = loc['location_id']
                flit_info = {
                    'global_id': gid,
                    'src': loc['src'],
                    'dest': loc['dest'],
                    'pack_id': loc['pack_id'],
                    'flit_id': loc['flit_id']
                }
                snapshot['routers'][router_id].append(flit_info)
            
            elif loc['location_type'] == 'link' and loc['location_id'] is not None:
                link_id = loc['location_id']
                flit_info = {
                    'global_id': gid,
                    'src': loc['src'],
                    'dest': loc['dest'],
                    'pack_id': loc['pack_id'],
                    'flit_id': loc['flit_id']
                }
                snapshot['links'][link_id].append(flit_info)
        
        tick_states[tick] = snapshot
    
    return tick_states

# ========== Step 2. Build Mesh XY topology ==========
def build_mesh_xy(n):
    """
    Return router positions + link mapping
    routers: {id: (x,y)}
    links: {lid: (src,dst)}
    """
    routers = {r: (r // n, r % n) for r in range(n*n)}
    links = {}
    lid = 0
    link_count=0
    # East output to West input links (weight = 1)
    for row in range(n):
        for col in range(n):
            if col + 1 < n:
                east_out = col + (row * n)
                west_in = (col + 1) + (row * n)
                links[link_count]=(east_out,west_in)
                link_count += 1

    # West output to East input links (weight = 1)
    for row in range(n):
        for col in range(n):
            if col + 1 < n:
                east_in = col + (row * n)
                west_out = (col + 1) + (row * n)
                links[link_count]=(west_out,east_in)
                link_count += 1

    # North output to South input links (weight = 2)
    for col in range(n):
        for row in range(n):
            if row + 1 < n:
                north_out = col + (row * n)
                south_in = col + ((row + 1) * n)
                links[link_count]=(north_out,south_in)
                link_count += 1

    # South output to North input links (weight = 2)
    for col in range(n):
        for row in range(n):
            if row + 1 < n:
                north_in = col + (row * n)
                south_out = col + ((row + 1) * n)
                links[link_count]=(south_out,north_in)
                link_count += 1
    # for y in range(n):
    #     for x in range(n):
    #         r = y*n + x
    #         # east
    #         if x < n-1:
    #             links[lid] = (r, r+1)
    #             lid += 1
    #         # south
    #         if y < n-1:
    #             links[lid] = (r, r+n)
    #             lid += 1
    return routers, links

# ========== Step 3. Generate Plotly animation ==========
def make_animation(snapshots, routers, links, interval=250):
    ticks_all = sorted(snapshots.keys())
    if not ticks_all:
        raise ValueError("No ticks found in snapshots! Check your log parsing.")

    # Group by interval
    max_tick = ticks_all[-1]
    ticks = list(range(0, max_tick+1, interval))

    frames = []

    for t in ticks:
        # Find most recent snapshot <= t
        available_ticks = [tk for tk in ticks_all if tk <= t]
        if available_ticks:
            snap = snapshots[available_ticks[-1]]
        else:
            snap = {"routers": defaultdict(list), "links": defaultdict(list)}

        # ----- Routers -----
        xs = [routers[r][0] for r in routers]
        ys = [routers[r][1] for r in routers]
        sizes = [len(snap["routers"].get(r, []))*5+10 for r in routers]
        colors = ["green" if len(snap["routers"].get(r, [])) > 0 else "steelblue" for r in routers]
        
        hover_texts = []
        for r in routers:
            flits = snap["routers"].get(r, [])
            if flits:
                flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                             for f in flits]
                flit_info = "<br>".join(flit_lines)
                hover_texts.append(f"<b>Router {r}</b><br>Flits: {len(flits)}<br>{flit_info}")
            else:
                hover_texts.append(f"<b>Router {r}</b><br>No flits")

        # ----- Links -----
        link_traces = []
        for lid, (a, b) in links.items():
            x0, y0 = routers[a]
            x1, y1 = routers[b]
            
            # Get flits on this link
            flits = snap["links"].get(lid, [])
            if a > b:
                flits1 = snap["links"].get(lid-12,[])
            else:
                flits1 = snap["links"].get(lid+12,[])
            
            # Link hover text
            if flits:
                flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                             for f in flits]
                flit_info = "<br>".join(flit_lines)
                hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>Flits: {len(flits)}<br>{flit_info}"
            else:
                hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>No flits"
            
            # Link width based on flit count
            line_width = max(2, len(flits) * 2)
            
            flag = len(flits1) > 0 or len(flits) > 0
            
            line_color = "red" if flag else "lightgray"
            
            #line_color = "red" if len(flits) > 0 else "lightgray"
            
            link_traces.append(
                go.Scatter(
                    x=[x0, x1], y=[y0, y1],
                    mode="lines",
                    line=dict(color=line_color, width=line_width),
                    text=hover_text,
                    hoverinfo="text",
                    showlegend=False
                )
            )

        frames.append(go.Frame(
            data=link_traces + [
                go.Scatter(x=xs, y=ys, mode="markers",
                           marker=dict(size=sizes, color=colors, 
                                     line=dict(width=2, color="darkblue")),
                           text=hover_texts,
                           hoverinfo="text",
                           showlegend=False),
            ],
            name=str(t)
        ))

    # Initial frame
    t0 = ticks[0]
    snap = snapshots.get(t0, {"routers": defaultdict(list), "links": defaultdict(list)})
    xs = [routers[r][0] for r in routers]
    ys = [routers[r][1] for r in routers]
    sizes = [len(snap["routers"].get(r, []))*5+10 for r in routers]
    
    hover_texts = []
    for r in routers:
        flits = snap["routers"].get(r, [])
        if flits:
            flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                         for f in flits]
            flit_info = "<br>".join(flit_lines)
            hover_texts.append(f"<b>Router {r}</b><br>Flits: {len(flits)}<br>{flit_info}")
        else:
            hover_texts.append(f"<b>Router {r}</b><br>No flits")

    # Initial links
    initial_link_traces = []
    for lid, (a, b) in links.items():
        x0, y0 = routers[a]
        x1, y1 = routers[b]
        
        flits = snap["links"].get(lid, [])
        
        if flits:
            flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                         for f in flits]
            flit_info = "<br>".join(flit_lines)
            hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>Flits: {len(flits)}<br>{flit_info}"
        else:
            hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>No flits"
        
        line_width = max(2, len(flits) * 2)
        line_color = "red" if len(flits) > 0 else "lightgray"
        
        initial_link_traces.append(
            go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=line_color, width=line_width),
                text=hover_text,
                hoverinfo="text",
                showlegend=False
            )
        )

    fig = go.Figure(
        data=initial_link_traces + [
            go.Scatter(x=xs, y=ys, mode="markers",
                       marker=dict(size=sizes, color="steelblue",
                                 line=dict(width=2, color="darkblue")),
                       text=hover_texts,
                       hoverinfo="text",
                       showlegend=False),
        ],
        layout=go.Layout(
            title=f"4x4 Mesh Network Flit Tracker (Step: {interval} ticks)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            hovermode='closest',
            plot_bgcolor='white',
            updatemenus=[{
                "buttons": [
                    {"args": [None, {"frame": {"duration": 500, "redraw": True},
                                     "fromcurrent": True}],
                     "label": "▶ Play",
                     "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": True},
                                       "mode": "immediate",
                                       "transition": {"duration": 0}}],
                     "label": "⏸ Pause",
                     "method": "animate"},
                ],
                "direction": "left",
                "pad": {"r": 10, "t": 87},
                "type": "buttons",
                "x": 0.1,
                "y": 1.15,
            }],
            sliders=[{
                "active": 0,
                "steps": [
                    {"args": [[str(t)], {"frame": {"duration": 0, "redraw": True},
                                         "mode": "immediate",
                                         "transition": {"duration": 0}}],
                     "label": f"T={t}",
                     "method": "animate"}
                    for t in ticks
                ],
                "x": 0.1,
                "len": 0.85,
                "xanchor": "left",
                "y": 0,
                "yanchor": "top",
            }]
        ),
        frames=frames
    )
    return fig

# ========== Run ==========
if __name__ == "__main__":
    print("Parsing log file...")
    snapshots = parse_log("processed.txt")
    print(f"Found {len(snapshots)} tick snapshots")
    
    # Debug: Check which link IDs appear in the log
    all_link_ids = set()
    for tick, snap in snapshots.items():
        all_link_ids.update(snap['links'].keys())
    print(f"\nLink IDs found in log: {sorted(all_link_ids)}")
    
    # Debug: print first few snapshots
    print("\nFirst 5 tick snapshots:")
    for tick in sorted(snapshots.keys())[:5]:
        print(f"\nTick {tick}:")
        snap = snapshots[tick]
        for rid, flits in snap['routers'].items():
            print(f"  Router {rid}: {[f['global_id'] for f in flits]}")
        for lid, flits in snap['links'].items():
            print(f"  Link {lid}: {[f['global_id'] for f in flits]}")
    
    routers, links = build_mesh_xy(4)
    print(f"\nGenerated links (our mapping): {links}")
    
    fig = make_animation(snapshots, routers, links, interval=250)
    fig.show()