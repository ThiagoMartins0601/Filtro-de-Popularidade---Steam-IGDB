import json
import os
import networkx as nx
from collections import defaultdict

class FixedLightGraphVisualizer:
    def __init__(self, json_path: str = "Dados Numericos/bancodados_clusterizado_caso1.json"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_path = os.path.join(current_dir, json_path)
        if not os.path.exists(self.file_path):
            self.file_path = os.path.join(current_dir, "Dados Numericos", "bancodados_clusterizado.json")
        self.output_html = os.path.join(current_dir, "Dados Numericos", "visualizacao_grafos_otimizada.html")
        self.games = self._load_data()

    def _load_data(self) -> list:
        if not os.path.exists(self.file_path):
            print(f"[ERRO] Arquivo não encontrado: {self.file_path}")
            return []
        with open(self.file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("[ERRO] Arquivo JSON corrompido.")
                return []

    def calculate_similarity(self, game_a: dict, game_b: dict) -> float:
        metrics_a = game_a.get("numerical_metrics", {})
        metrics_b = game_b.get("numerical_metrics", {})

        genres_a = set([g.strip().lower() for g in game_a.get("genres_string", "").split(",") if g.strip() and g.strip().lower() != "unknown"])
        genres_b = set([g.strip().lower() for g in game_b.get("genres_string", "").split(",") if g.strip() and g.strip().lower() != "unknown"])
        
        if genres_a or genres_b:
            intersection = len(genres_a.intersection(genres_b))
            union = len(genres_a.union(genres_b))
            genre_sim = intersection / union if union > 0 else 0.0
        else:
            genre_sim = 0.0

        rating_a = metrics_a.get("igdb_rating_raw", 0) or metrics_a.get("critic_score_raw", 0)
        rating_b = metrics_b.get("igdb_rating_raw", 0) or metrics_b.get("critic_score_raw", 0)
        rating_sim = 1.0 - (abs(rating_a - rating_b) / 100.0)

        return (genre_sim * 0.7) + (rating_sim * 0.3)

    def generate_dashboard(self):
        if not self.games:
            print("[ERRO] Nenhum jogo carregado.")
            return

        genre_buckets = defaultdict(list)
        tier_colors = {
            0: "#c28b38", # Âncora / Hub Dijkstra (iRacing / Destaques)
            1: "#a855f7",
            2: "#10b981",
            3: "#3b82f6",
            4: "#6b7280"  # Periférico
        }

        for game in self.games:
            genres_str = game.get("genres_string", "Unknown")
            primary_genre = genres_str.split(",")[0].strip().title() if genres_str else "Outros"
            genre_buckets[primary_genre].append(game)

        light_genres_data = {}

        print("Processando dados e gerando pacotes visuais leves...")

        for genre, games_list in genre_buckets.items():
            if len(games_list) < 3:
                continue

            games_list.sort(key=lambda g: (g.get("cluster_id", 4), -(g.get("numerical_metrics", {}).get("igdb_rating_raw", 0))))
            batch_games = games_list[:2000] 
            n = len(batch_games)

            G = nx.Graph()
            for i in range(n):
                G.add_node(i)

            edges = []
            for i in range(n):
                for j in range(i + 1, n):
                    sim = self.calculate_similarity(batch_games[i], batch_games[j])
                    if sim >= 0.58: 
                        G.add_edge(i, j, weight=sim)
                        edges.append({
                            "from": i,
                            "to": j,
                            "width": max(1, sim * 1.5),
                            "color": {"color": "#4b5563", "opacity": 0.5}
                        })

            pos = nx.spring_layout(G, weight='weight', k=0.35, iterations=60, seed=42)

            if pos:
                xs = [c[0] for c in pos.values()]
                ys = [c[1] for c in pos.values()]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                rx, ry = (max_x - min_x) or 1.0, (max_y - min_y) or 1.0
                
                norm_pos = {node: (((x - min_x) / rx) * 800 - 400, ((y - min_y) / ry) * 800 - 400) for node, (x, y) in pos.items()}
            else:
                norm_pos = pos

            nodes = []
            for i, game in enumerate(batch_games):
                tier = game.get("cluster_id", 2)
                color = tier_colors.get(tier, "#3b82f6")
                title = game.get("title", "Desconhecido").replace('"', "'")
                rating = game.get("numerical_metrics", {}).get("igdb_rating_raw", 0) or game.get("numerical_metrics", {}).get("critic_score_raw", 0)
                
                x, y = norm_pos.get(i, (0, 0))
                nodes.append({
                    "id": i,
                    "label": title[:16] + "..." if len(title) > 16 else title,
                    "title": f"<b>{title}</b><br>Tier Dijkstra: #{tier}<br>Nota: {rating}",
                    "x": float(x),
                    "y": float(y),
                    "fixed": True,
                    "color": {"background": color, "border": "#ffffff" if tier == 0 else color},
                    "borderWidth": 3 if tier == 0 else 1,
                    "size": 18 if tier == 0 else 11
                })

            light_genres_data[genre] = {
                "total": len(games_list),
                "nodes": nodes,
                "edges": edges
            }

        html_content = f"""<!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Protocol Kodexia — Grafo Otimizado</title>
            <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
            <style>
                :root {{ --bg: #0f1115; --card: #181b22; --text: #e5e7eb; --accent: #c28b38; }}
                body {{ font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
                header {{ text-align: center; margin-bottom: 15px; border-bottom: 1px solid #2d3748; padding-bottom: 10px; }}
                h1 {{ color: var(--accent); margin: 0; }}
                .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 15px; }}
                .tab {{ background: var(--card); color: var(--text); border: 1px solid #2d3748; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em; transition: 0.2s; }}
                .tab.active, .tab:hover {{ background: var(--accent); color: #0f1115; font-weight: bold; border-color: var(--accent); }}
                #container {{ width: 100%; max-width: 3000px; max-height: 1900px; height: 720px; background: var(--card); border: 1px solid #2d3748; border-radius: 12px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
                .info {{ text-align: center; color: #9ca3af; margin-top: 12px; font-size: 1em; }}
            </style>
        </head>
        <body>
            <header>
                <h1>Protocol Kodexia — Visualização de Grafos por Gênero</h1>
                <p style="color: #9ca3af; margin: 4px 0 0 0;">Otimizado, leve e restrito à resolução máxima de 3000x1900</p>
            </header>
            <div class="tabs" id="tabs"></div>
            <div id="container"></div>
            <div class="info" id="info">Selecione uma categoria acima...</div>

            <script>
                const db = {json.dumps(light_genres_data)};
                let net = null;
                const tabsContainer = document.getElementById('tabs');
                const keys = Object.keys(db).sort();

                keys.forEach(k => {{
                    let b = document.createElement('button');
                    b.className = 'tab';
                    b.textContent = `${{k}} (${{db[k].nodes.length}})`;
                    b.onclick = () => loadGenre(k);
                    tabsContainer.appendChild(b);
                }});

                function loadGenre(k) {{
                    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent.startsWith(k)));
                    let data = db[k];
                    document.getElementById('info').innerHTML = `Gênero: <b>${{k}}</b> | Exibindo ${{data.nodes.length}} nós e ${{data.edges.length}} arestas conectadas`;

                    let container = document.getElementById('container');
                    let netData = {{ 
                        nodes: new vis.DataSet(data.nodes), 
                        edges: new vis.DataSet(data.edges) 
                    }};
                    
                    let options = {{
                        nodes: {{ 
                            shape: 'dot', 
                            font: {{ face: 'Segoe UI', size: 11, color: '#e5e7eb', background: '#181b22', strokeWidth: 1, strokeColor: '#181b22' }} 
                        }},
                        edges: {{ 
                            smooth: false,
                            color: {{ color: '#4b5563', highlight: '#c28b38' }}
                        }},
                        physics: false,
                        interaction: {{ hover: true, tooltipDelay: 50 }}
                    }};

                    if (net) {{
                        net.destroy();
                    }}
                    net = new vis.Network(container, netData, options);
                }}

                if (keys.length > 0) {{
                    loadGenre(keys[0]);
                }}
            </script>
        </body>
        </html>
        """

        with open(self.output_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[SUCESSO] Dashboard leve e corrigido gerado em: {self.output_html}")

if __name__ == "__main__":
    vis = FixedLightGraphVisualizer()
    vis.generate_dashboard()