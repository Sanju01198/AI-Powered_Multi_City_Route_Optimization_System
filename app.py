import gradio as gr
import requests
import numpy as np
import time
from datetime import datetime, timedelta
import folium
from folium.plugins import PolyLineTextPath

# ============================================================
# UTILITIES
# ============================================================

def get_coordinates(city):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "VRPTW-Gradio-App"}
    res = requests.get(url, params=params, headers=headers, timeout=10)
    data = res.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    raise ValueError(f"Coordinates not found for {city}")

def haversine_distance(c1, c2):
    lat1, lon1 = c1
    lat2, lon2 = c2
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371
    distance_km = r * c
    time_minutes = (distance_km * 1.3 / 50) * 60
    return distance_km * 1.3, time_minutes

def get_osrm_distance_time(c1, c2, max_retries=3):
    lat1, lon1 = c1
    lat2, lon2 = c2
    for attempt in range(max_retries):
        try:
            url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            res = requests.get(url, timeout=15)
            data = res.json()
            if data["code"] == "Ok":
                return (data["routes"][0]["distance"] / 1000, data["routes"][0]["duration"] / 60)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < max_retries - 1:
                time.sleep(2)
            continue
        except:
            break
    return haversine_distance(c1, c2)

def sanitize_coord(coord):
    a, b = coord
    return (b, a) if abs(a) > 90 else (a, b)

# ============================================================
# ROUTING ALGORITHM
# ============================================================

def run_vrptw(vehicles, demands, cities, coords, distance_matrix, depot):
    SPEED_KMPH = 60
    UNLOAD_MIN_PER_100KG = 30
    demands_copy = {d['city']: {'remaining': d['demand']} for d in demands}
    
    def travel_time_minutes(a, b):
        i, j = cities.index(a), cities.index(b)
        return (distance_matrix[i][j] / SPEED_KMPH) * 60
    
    def dist_between(a, b):
        i, j = cities.index(a), cities.index(b)
        return distance_matrix[i][j]
    
    def simulate_vehicle(vehicle, demands):
        start_dt = datetime.strptime(f"{vehicle['startDate']} {vehicle['startTime']}", "%Y-%m-%d %H:%M")
        time_var = start_dt
        location = depot
        capacity = vehicle['capacity']
        route = []
        demand_cities = list(demands.keys())
        
        for city in demand_cities:
            while demands[city]['remaining'] > 0:
                if capacity > 0:
                    travel_min = travel_time_minutes(location, city)
                    arrive = time_var + timedelta(minutes=travel_min)
                    deliver = min(capacity, demands[city]['remaining'])
                    unload = (deliver / 100) * UNLOAD_MIN_PER_100KG
                    route.append({
                        'from': location, 'to': city, 'depart': time_var,
                        'arrive': arrive, 'deliver': deliver, 'unload': unload,
                        'distance': dist_between(location, city)
                    })
                    time_var = arrive + timedelta(minutes=unload)
                    demands[city]['remaining'] -= deliver
                    capacity -= deliver
                    location = city
                else:
                    refill_time = travel_time_minutes(location, depot) + travel_time_minutes(depot, city)
                    new_vehicle_time = travel_time_minutes(depot, city)
                    if refill_time <= new_vehicle_time:
                        back = travel_time_minutes(location, depot)
                        arrive_depot = time_var + timedelta(minutes=back)
                        route.append({
                            'from': location, 'to': depot, 'depart': time_var,
                            'arrive': arrive_depot, 'deliver': 0, 'unload': 0,
                            'distance': dist_between(location, depot)
                        })
                        time_var = arrive_depot
                        location = depot
                        capacity = vehicle['capacity']
                    else:
                        break
        
        if location != depot:
            back = travel_time_minutes(location, depot)
            arrive_depot = time_var + timedelta(minutes=back)
            route.append({
                'from': location, 'to': depot, 'depart': time_var,
                'arrive': arrive_depot, 'deliver': 0, 'unload': 0,
                'distance': dist_between(location, depot)
            })
        return route
    
    solution = {}
    for v in vehicles:
        if any(d['remaining'] > 0 for d in demands_copy.values()):
            route = simulate_vehicle(v, demands_copy)
            if route:
                solution[v['id']] = route
    return solution

# ============================================================
# PROCESSING FUNCTIONS
# ============================================================

def process_vehicles(vehicle_data):
    vehicles = []
    if not vehicle_data or not vehicle_data.strip():
        return vehicles
    lines = vehicle_data.strip().split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                try:
                    vehicles.append({
                        'id': i + 1,
                        'capacity': float(parts[0]),
                        'startDate': parts[1],
                        'startTime': parts[2]
                    })
                except:
                    pass
    return vehicles

def process_demands(demand_data):
    demands = []
    if not demand_data or not demand_data.strip():
        return demands
    lines = demand_data.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                try:
                    city = ', '.join(parts[:-3])
                    demand_val = float(parts[-3])
                    tw_start = parts[-2]
                    tw_end = parts[-1]
                    demands.append({
                        'city': city, 'demand': demand_val,
                        'tw_start': tw_start, 'tw_end': tw_end
                    })
                except:
                    pass
    return demands

def build_matrices(supply_location, vehicles, demands, progress=gr.Progress()):
    progress(0, desc="Starting...")
    cities = [supply_location] + [d['city'] for d in demands]
    coords = {}
    
    progress(0.2, desc="Fetching coordinates...")
    for i, city in enumerate(cities):
        lat, lon = get_coordinates(city)
        coords[city] = (lat, lon)
        time.sleep(1)
        progress(0.2 + (0.3 * (i + 1) / len(cities)), desc=f"Got coordinates for {city}")
    
    n = len(cities)
    D = np.zeros((n, n))
    progress(0.5, desc="Computing distances...")
    total_pairs = n * (n - 1)
    pair_count = 0
    
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j], _ = get_osrm_distance_time(coords[cities[i]], coords[cities[j]])
                time.sleep(0.5)
                pair_count += 1
                progress(0.5 + (0.4 * pair_count / total_pairs), desc=f"Computing routes...")
    
    progress(0.9, desc="Building solution...")
    return cities, coords, D

def generate_routes(supply_location, vehicle_data, demand_data, progress=gr.Progress()):
    try:
        if not supply_location or not supply_location.strip():
            return "❌ Error: Please provide supply location", "", "<p>No map available</p>"
        
        vehicles = process_vehicles(vehicle_data)
        demands = process_demands(demand_data)
        
        if not vehicles:
            return "❌ Error: Please provide at least one vehicle", "", "<p>No map available</p>"
        if not demands:
            return "❌ Error: Please provide at least one demand", "", "<p>No map available</p>"
        
        cities, coords, distance_matrix = build_matrices(supply_location.strip(), vehicles, demands, progress)
        solution = run_vrptw(vehicles, demands, cities, coords, distance_matrix, supply_location.strip())
        
        if not solution:
            return "❌ Error: No solution found", "", "<p>No map available</p>"
        
        routes_text = generate_routes_text(solution, supply_location.strip())
        summary_text = generate_summary(solution, cities, supply_location.strip(), distance_matrix)
        map_html = generate_map(solution, coords, supply_location.strip())
        
        progress(1.0, desc="Complete!")
        return routes_text, summary_text, map_html
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        return f"❌ Error: {str(e)}\n\nDetails:\n{error_details}", "", "<p>Error</p>"

def generate_routes_text(solution, depot):
    output = ["=" * 60, "🚚 VEHICLE ROUTES", "=" * 60, ""]
    for vid, route in solution.items():
        output.append(f"🚚 Vehicle {vid}")
        output.append("")
        for i, leg in enumerate(route, 1):
            tag = "REFILL/RETURN" if leg['to'] == depot else "DELIVERY"
            output.append(f"  ➤ Route {i}: {leg['from']} → {leg['to']} [{tag}]")
            output.append(f"     Depart  : {leg['depart'].strftime('%d %b %Y, %I:%M %p')}")
            output.append(f"     Arrive  : {leg['arrive'].strftime('%d %b %Y, %I:%M %p')}")
            output.append(f"     Distance: {leg['distance']:.2f} km")
            if leg['deliver'] > 0:
                output.append(f"     Unload  : {leg['deliver']:.0f} kg ({leg['unload']:.0f} min)")
            output.append("")
        output.append("-" * 60)
        output.append("")
    return "\n".join(output)

def generate_summary(solution, cities, depot, distance_matrix):
    total_distance = 0
    max_time = 0
    bottleneck_vehicle = None
    vehicle_stats = []
    
    for vid, route in solution.items():
        visited = []
        dist = 0
        start = route[0]['depart']
        end = route[-1]['arrive']
        for leg in route:
            if leg['from'] not in visited:
                visited.append(leg['from'])
            if leg['to'] not in visited:
                visited.append(leg['to'])
            dist += leg['distance']
        time_hours = (end - start).total_seconds() / 3600
        avg_speed = dist / time_hours if time_hours > 0 else 0
        vehicle_stats.append({
            'id': vid, 'route': visited, 'distance': dist,
            'time': time_hours, 'avg_speed': avg_speed
        })
        total_distance += dist
        if time_hours > max_time:
            max_time = time_hours
            bottleneck_vehicle = vid
    
    summary = []
    summary.append("📊 OVERALL DELIVERY SUMMARY")
    summary.append("")
    summary.append(f"Used {len(solution)} vehicle(s) to fulfill all demands.")
    summary.append(f"Total distance: {total_distance:.2f} km")
    summary.append(f"Completion time: {max_time:.2f} hours")
    summary.append("")
    summary.append("🚚 VEHICLE INSIGHTS")
    summary.append("")
    for v in vehicle_stats:
        summary.append(f"Vehicle {v['id']}: {' → '.join(v['route'])}")
        summary.append(f"  {v['distance']:.2f} km | {v['time']:.2f} hrs | {v['avg_speed']:.2f} km/h")
        summary.append("")
    summary.append("🚨 BOTTLENECK ANALYSIS")
    summary.append("")
    summary.append(f"Vehicle {bottleneck_vehicle} determines overall completion time.")
    summary.append("")
    summary.append("💡 OPTIMIZATION SUGGESTIONS")
    summary.append("- Add vehicles to reduce bottlenecks")
    summary.append("- Assign high-capacity vehicles to long routes")
    summary.append("- Greedy refill-aware strategy ensures realism")
    return "\n".join(summary)

def generate_map(solution, coords, depot):
    try:
        coords_clean = {city: sanitize_coord(c) for city, c in coords.items()}
        lats = [lat for lat, lon in coords_clean.values()]
        lons = [lon for lat, lon in coords_clean.values()]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        m = folium.Map(tiles="CartoDB positron", control_scale=True, zoom_control=True)
        m.fit_bounds([[min_lat - 1, min_lon - 1], [max_lat + 1, max_lon + 1]], padding=(30, 30))
        
        depot_lat, depot_lon = coords_clean[depot]
        folium.Marker([depot_lat, depot_lon], icon=folium.Icon(color="red", icon="star", prefix="fa"),
            tooltip=f"SUPPLY: {depot}").add_to(m)
        
        for city, (lat, lon) in coords_clean.items():
            if city != depot:
                folium.CircleMarker([lat, lon], radius=5, color="black", fill=True,
                    fill_color="white", tooltip=city).add_to(m)
        
        vehicle_colors = ["blue", "green", "purple", "orange", "darkred"]
        def offset_point(p, off):
            return (p[0] + off, p[1] + off)
        
        for v_idx, (vid, route) in enumerate(solution.items()):
            color = vehicle_colors[v_idx % len(vehicle_colors)]
            offset = 0.03 * v_idx
            for step_idx, leg in enumerate(route, start=1):
                lat1, lon1 = offset_point(coords_clean[leg['from']], offset)
                lat2, lon2 = offset_point(coords_clean[leg['to']], offset)
                polyline = folium.PolyLine([[lat1, lon1], [lat2, lon2]], color=color, weight=3,
                    opacity=0.9, tooltip=f"Vehicle {vid} | Route {step_idx}").add_to(m)
                PolyLineTextPath(polyline, text=str(step_idx), repeat=False, offset=7,
                    attributes={"fill": color, "font-weight": "bold", "font-size": "12"}).add_to(m)
        
        return m._repr_html_()
    except Exception as e:
        return f"<p>Error: {str(e)}</p>"

# ============================================================
# GRADIO INTERFACE
# ============================================================

with gr.Blocks(title="VRPTW Routing System", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🚚 VRPTW Routing System\n### Vehicle Routing Problem with Time Windows")
    
    with gr.Tab("📥 Input"):
        gr.Markdown("## Supply Location")
        supply_input = gr.Textbox(label="Supply Point", placeholder="e.g., Mumbai, India", lines=1)
        
        gr.Markdown("## Vehicles")
        gr.Markdown("**Format:** `capacity, start_date, start_time` (one per line)")
        vehicle_input = gr.Textbox(label="Vehicle Data", 
            placeholder="1000, 2025-01-15, 08:00\n1200, 2025-01-15, 09:00", lines=5)
        
        gr.Markdown("## Demands")
        gr.Markdown("**Format:** `city, demand_kg, tw_start, tw_end` (one per line)")
        demand_input = gr.Textbox(label="Demand Data",
            placeholder="Delhi India, 500, 09:00, 17:00\nBangalore India, 800, 10:00, 18:00", lines=5)
        
        generate_btn = gr.Button("🚀 Generate Routes", variant="primary", size="lg")
    
    with gr.Tab("📊 Results"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🚚 Vehicle Routes")
                routes_output = gr.Textbox(label="Detailed Routes", lines=25, max_lines=50, show_label=False)
            
            with gr.Column(scale=1):
                gr.Markdown("### 📈 AI Summary")
                summary_output = gr.Textbox(label="Analysis & Insights", lines=25, show_label=False)
        
        gr.Markdown("### 🗺️ Route Map")
        map_output = gr.HTML(label="Interactive Map")
    
    generate_btn.click(fn=generate_routes, inputs=[supply_input, vehicle_input, demand_input],
        outputs=[routes_output, summary_output, map_output])
    
    gr.Examples(
        examples=[["Mumbai, India", "1000, 2025-01-15, 08:00\n1200, 2025-01-15, 08:30",
            "Delhi India, 800, 09:00, 17:00\nBangalore India, 600, 10:00, 18:00\nChennai India, 400, 09:00, 16:00"]],
        inputs=[supply_input, vehicle_input, demand_input]
    )

app.launch()