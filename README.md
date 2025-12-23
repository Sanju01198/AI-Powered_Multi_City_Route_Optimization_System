# 🚚 VRPTW Routing System  
### AI-Powered Multi-City Route Optimization System

A production-ready **Vehicle Routing Problem with Time Windows (VRPTW)** solver that optimizes delivery routes across multiple cities using **real-world road distances**, **capacity-aware routing**, and **interactive visualization**.

---

## 📌 Overview

The **VRPTW Routing System** is an advanced logistics optimization tool designed to solve **real-world routing problems** involving:

- Multiple vehicles  
- Capacity constraints  
- Delivery demands  
- Time windows  
- Refill decisions  
- Real road distances  

It combines **algorithmic optimization**, **geospatial APIs**, and a **modern web UI** to provide actionable logistics insights.

---

## 🚛 What is VRPTW?

The **Vehicle Routing Problem with Time Windows (VRPTW)** is an extension of the classic **Vehicle Routing Problem (VRP)**, itself a generalization of the **Travelling Salesman Problem (TSP)**.

- NP-Hard optimization problem  
- Widely used in logistics & supply chains  
- Requires heuristic or meta-heuristic solutions  

---

## ✨ Key Capabilities

- Multi-vehicle routing with heterogeneous capacities  
- Real-world routing using OpenStreetMap + OSRM  
- Capacity-aware refill decisions  
- Partial deliveries & split shipments  
- Interactive map visualization  
- AI-generated analytics & bottleneck detection  

---

## 🖥️ Interface Overview

**Tabs Included**
1. Input Configuration  
2. Vehicle Routes  
3. AI Summary  
4. Interactive Map  

---

## 🛠️ Installation

```bash
git clone https://github.com/yourusername/vrptw-routing-system.git
cd vrptw-routing-system
pip install -r requirements.txt
python app.py
```

---

## 📥 Input Format

### Supply Location
```
Mumbai India
```

### Vehicle Data
```
1000, 2025-01-15, 08:00
1200, 2025-01-15, 08:30
```

### Demand Data
```
Delhi India, 800, 09:00, 17:00
```

---

## 🧠 Algorithm

- Greedy refill-aware VRPTW heuristic  
- OSRM-based distance calculation  
- Haversine fallback  
- Capacity-based vehicle routing  

---

## 📊 Output

- Optimized routes per vehicle  
- Total distance & time  
- Bottleneck analysis  
- Interactive Folium map  

---

## 🔮 Future Enhancements

- Genetic Algorithm / Meta-heuristics  
- Strict time window enforcement  
- Traffic-aware routing  
- Multi-depot support  

---

## 🔗 Links

Live Demo: https://huggingface.co/spaces/Sanju01198/AI-Powered_Multi-City_Route_Optimization_System  
GitHub: https://github.com/Sanju01198/AI-Powered_Multi_City_Route_Optimization_System
Demo video: https://drive.google.com/file/d/1GUPkIJgfsSeYqyjBFau3NPWxh7_70i_9/view?usp=sharing
