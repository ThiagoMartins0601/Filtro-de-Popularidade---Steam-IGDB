import json
import os
import math
import random
import time
import pandas as pd
import networkx as nx
from collections import defaultdict, Counter
from typing import Dict, List, Any

class MarketIntelligencePipeline:
    def __init__(self, target_count: int = 500, top_n_visual: int = 150, kaggle_json: str = "games.json", legacy_json: str = "bancodados_completo.json", csv_dataset: str = "dataset.csv", output_filename: str = "bancodados_comparativo_final.json", freq_filename: str = "frequencia_reviews.json", html_output: str = "rede_inteligencia_mercado.html", chunk_size: int = 50000):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, "Dados Numericos")
        self.kaggle_path = os.path.join(self.data_dir, kaggle_json)
        self.legacy_path = os.path.join(self.data_dir, legacy_json)
        self.csv_path = os.path.join(self.data_dir, csv_dataset)
        self.output_path = os.path.join(self.data_dir, output_filename)
        self.freq_output_path = os.path.join(self.data_dir, freq_filename)
        self.html_path = os.path.join(current_dir, html_output)
        self.chunk_size = chunk_size
        self.target_count = target_count
        self.top_n_visual = top_n_visual

    def _load_json(self, path: str) -> Any:
        if not os.path.exists(path):
            print(f"[AVISO] Arquivo não encontrado: {path}", flush=True)
            return None
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return None

    def _normalize(self, text: str) -> str:
        """Normalização rigorosa para garantir match perfeito entre strings."""
        if not text or pd.isna(text):
            return ""
        cleaned = "".join([c for c in str(text).lower() if c.isalnum() or c.isspace()])
        return " ".join(cleaned.split())

    def extract_critical_keywords(self, texts: List[str], top_n: int = 20) -> List[Dict]:
        """Filtra stopwords bilíngues e extrai termos críticos (tokens > 2 para capturar bug, lag, bad, fun)."""
        stopwords = {
            "the", "and", "to", "a", "of", "in", "for", "is", "on", "that", "this", "it", 
            "with", "as", "was", "you", "but", "are", "they", "be", "at", "one", "have", 
            "game", "play", "playing", "so", "from", "an", "or", "just", "if", "out",
            "about", "all", "get", "when", "like", "not", "good", "great", "very", "i", "my",
            "its", "has", "can", "do", "would", "he", "she", "they", "than", "ion", "there",
            "time", "hours", "will", "back", "make", "know", "player", "players",
            "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não",
            "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi",
            "ao", "ele", "das", "seu", "sua", "ou", "quando", "muito", "nos", "já", "está",
            "eu", "também", "só", "pelo", "pela", "até", "essa", "entre", "depois", "sem",
            "mesmo", "aos", "ter", "seus", "quem", "nas", "esse", "eles", "você", "num",
            "nem", "suas", "meu", "minha", "tinha", "jogo", "jogos", "faz", "tem", "horas",
            "bom", "bem", "ainda", "fazer", "pode", "esse", "essa"
        }
        
        words = []
        for text in texts:
            if not text or pd.isna(text):
                continue
            cleaned = "".join([c if c.isalnum() or c.isspace() else " " for c in str(text).lower()])
            for token in cleaned.split():
                if len(token) > 2 and token not in stopwords:
                    words.append(token)
        
        counter = Counter(words)
        return [{"word": w, "frequency": f} for w, f in counter.most_common(top_n)]

    def process_dataset_with_pandas(self) -> Dict[str, Dict]:
        """Lê o dataset.csv em lotes usando Pandas, agregando reviews e calculando frequências."""
        if not os.path.exists(self.csv_path):
            print(f"[ALERTA CRÍTICIO] dataset.csv não encontrado em {self.csv_path}.", flush=True)
            return {}

        print(f"[Pandas Engine] Lendo dataset.csv em blocos de {self.chunk_size} linhas...", flush=True)
        start_time = time.time()
        
        raw_reviews_aggregate = defaultdict(lambda: {
            "title": "",
            "positive_texts": [],
            "negative_texts": [],
            "positive_count": 0,
            "negative_count": 0
        })

        total_rows = 0
        try:
            for chunk in pd.read_csv(self.csv_path, chunksize=self.chunk_size, low_memory=False, on_bad_lines='skip'):
                chunk.columns = [str(c).strip().lower() for c in chunk.columns]
                
                name_col = next((c for c in chunk.columns if 'name' in c or 'title' in c), chunk.columns[1] if len(chunk.columns) > 1 else 'app_name')
                text_col = next((c for c in chunk.columns if 'text' in c or 'review' in c), chunk.columns[2] if len(chunk.columns) > 2 else 'review_text')
                score_col = next((c for c in chunk.columns if 'score' in c), chunk.columns[3] if len(chunk.columns) > 3 else 'review_score')

                for row in chunk.itertuples(index=False):
                    name = str(getattr(row, name_col, "")) if hasattr(row, name_col) else ""
                    text = str(getattr(row, text_col, "")) if hasattr(row, text_col) else ""
                    try:
                        score = int(float(getattr(row, score_col, 1)))
                    except (ValueError, TypeError):
                        score = 1

                    if not name or name.lower() == 'nan':
                        continue

                    norm_key = self._normalize(name)
                    if not norm_key:
                        continue

                    entry = raw_reviews_aggregate[norm_key]
                    if not entry["title"]:
                        entry["title"] = name

                    if score >= 1:
                        entry["positive_count"] += 1
                        if text and text.lower() != 'nan' and len(entry["positive_texts"]) < 50:
                            entry["positive_texts"].append(text)
                    else:
                        entry["negative_count"] += 1
                        if text and text.lower() != 'nan' and len(entry["negative_texts"]) < 50:
                            entry["negative_texts"].append(text)

                    total_rows += 1

                print(f" -> Lidas {total_rows} linhas | Jogos unificados: {len(raw_reviews_aggregate)}", end="\r", flush=True)

        except Exception as e:
            print(f"\n[ERRO] Falha ao processar CSV com Pandas: {e}", flush=True)

        print(f"\n[SUCESSO] Processamento do CSV via Pandas concluído em {time.time() - start_time:.2f}s. Jogos mapeados: {len(raw_reviews_aggregate)}\n", flush=True)
        
        final_frequency_db = {}
        for norm_key, data in raw_reviews_aggregate.items():
            pos_kw = self.extract_critical_keywords(data["positive_texts"], top_n=20)
            neg_kw = self.extract_critical_keywords(data["negative_texts"], top_n=20)
            
            final_frequency_db[norm_key] = {
                "title": data["title"],
                "positive_count": data["positive_count"],
                "negative_count": data["negative_count"],
                "review_word_frequencies": {
                    "positive_top_keywords": pos_kw,
                    "negative_top_keywords": neg_kw
                }
            }

        return final_frequency_db

    def load_and_merge_databases(self, target_count: int = 500) -> List[Dict]:
        print("[1/5] Sincronizando bases de dados com Pandas e indexação O(1)...", flush=True)
        
        review_freq_lookup = self.process_dataset_with_pandas()
        raw_kaggle = self._load_json(self.kaggle_path)
        raw_legacy = self._load_json(self.legacy_path)

        if not raw_kaggle:
            print(f"[ERRO CRÍTICO] Base do Kaggle não encontrada em: {self.kaggle_path}", flush=True)
            return []

        legacy_dict = {}
        if isinstance(raw_legacy, list):
            for g in raw_legacy:
                t = g.get("title", "")
                if t:
                    legacy_dict[self._normalize(t)] = g
        elif isinstance(raw_legacy, dict):
            for k, v in raw_legacy.items():
                legacy_dict[self._normalize(str(k))] = v

        merged_pool = []
        frequency_database_output = {}
        start_time = time.time()
        
        CONFIDENCE_WEIGHT = 50.0
        PRIOR_MEAN = 0.50

        matched_count = 0
        items_iterable = raw_kaggle.items() if isinstance(raw_kaggle, dict) else enumerate(raw_kaggle)
        total_items = len(raw_kaggle) if isinstance(raw_kaggle, dict) else len(raw_kaggle)

        for idx, (key, row) in enumerate(items_iterable, start=1):
            if not isinstance(row, dict):
                continue

            title = row.get("name") or row.get("title") or row.get("Name") or "Desconhecido"
            if not title or str(title).strip() in ["Desconhecido", ""]:
                continue

            norm_title = self._normalize(title)
            appid_str = str(key) if str(key).isdigit() else str(row.get("steam_appid", ""))

            matched_review_data = review_freq_lookup.get(norm_title, {
                "positive_count": int(row.get("positive") or 0),
                "negative_count": int(row.get("negative") or 0),
                "review_word_frequencies": {
                    "positive_top_keywords": [],
                    "negative_top_keywords": []
                }
            })

            if norm_title in review_freq_lookup:
                matched_count += 1

            pos_votes = float(matched_review_data["positive_count"])
            neg_votes = float(matched_review_data["negative_count"])
            total_votes = pos_votes + neg_votes

            bayesian_polarity = (pos_votes + (CONFIDENCE_WEIGHT * PRIOR_MEAN)) / (total_votes + CONFIDENCE_WEIGHT)
            word_freqs = matched_review_data["review_word_frequencies"]

            release_date = row.get("release_date") or row.get("Release Date") or "2020-01-01"
            year = "2020"
            for part in str(release_date).split("-") + str(release_date).split("/"):
                if part.strip().isdigit() and len(part.strip()) == 4:
                    year = part.strip()
                    break

            peak_ccu = float(row.get("peak_ccu") or 0)
            legacy_match = legacy_dict.get(norm_title, {})
            legacy_metrics = legacy_match.get("numerical_metrics", {})
            
            raw_rating = float(legacy_metrics.get("igdb_rating_raw") or row.get("metacritic_score") or row.get("user_score") or 0.0)
            igdb_rating = raw_rating if raw_rating > 0 else (40.0 if total_votes < 10 else 65.0)

            genres_raw = row.get("genres", legacy_match.get("genres_string", "Simulation, Action"))
            genres_str = ", ".join(genres_raw) if isinstance(genres_raw, list) else str(genres_raw)

            game_obj = {
                "title": str(title).strip(),
                "release_date": str(release_date).strip(),
                "release_year": str(year),
                "genres_string": genres_str,
                "steam_appid": int(appid_str) if appid_str.isdigit() else None,
                "numerical_metrics": {
                    "igdb_rating_raw": igdb_rating,
                    "community_polarity_score": round(bayesian_polarity, 4),
                    "positive_votes": int(pos_votes),
                    "negative_votes": int(neg_votes),
                    "total_votes": int(total_votes),
                    "current_steam_players_raw": peak_ccu,
                    "estimated_owners_raw": 5000
                },
                "review_word_frequencies": word_freqs,
                "market_intelligence": {
                    "sentiment_divergence": round(abs((igdb_rating / 10.0) - (bayesian_polarity * 10.0)), 2)
                }
            }

            merged_pool.append(game_obj)
            frequency_database_output[str(title).strip()] = {
                "steam_appid": game_obj["steam_appid"],
                "review_word_frequencies": word_freqs
            }

            if idx % 5000 == 0 or idx == total_items:
                elapsed = time.time() - start_time
                print(f"[Merge] Processados: {idx}/{total_items} ({idx/total_items*100:.1f}%) | Vinculados: {matched_count} | Tempo: {elapsed:.1f}s", end="\r", flush=True)

        print(f"\n[SUCESSO] Pool unificado: {len(merged_pool)} jogos | Com reviews associadas: {matched_count}\n", flush=True)

        if len(merged_pool) <= target_count:
            return merged_pool

        print(f"[2/5] Aplicando amostragem estratificada priorizada para {target_count} jogos...", flush=True)
        year_buckets = defaultdict(list)
        for game in merged_pool:
            year_buckets[game["release_year"]].append(game)

        quota = max(1, target_count // len(year_buckets))
        final_selected = []
        
        priority_keywords = ["counter-strike", "hades", "gta", "witcher", "skyrim", "dota", "portal", "cyberpunk", "iracing"]
        for bucket in year_buckets.values():
            bucket.sort(key=lambda g: (
                any(pk in g["title"].lower() for pk in priority_keywords),
                g["numerical_metrics"]["total_votes"],
                g["numerical_metrics"]["current_steam_players_raw"]
            ), reverse=True)
            final_selected.extend(bucket[:quota])

        if len(final_selected) < target_count:
            remaining = [g for g in merged_pool if g not in final_selected]
            remaining.sort(key=lambda g: g["numerical_metrics"]["total_votes"], reverse=True)
            final_selected.extend(remaining[:(target_count - len(final_selected))])

        print(f"[SUCESSO] Amostragem final de {len(final_selected)} jogos concluída.\n", flush=True)
        return final_selected[:target_count]

    def generate_html_visualization(self, games: List[Dict], G: nx.Graph, importance_scores: dict, frequency_database: Dict):
        sorted_indices = sorted(importance_scores.keys(), key=lambda k: importance_scores[k], reverse=True)
        visual_limit = max(150, self.top_n_visual)
        top_node_indices = set(sorted_indices[:visual_limit])

        nodes_list = []
        edges_list = []
        visual_freq_map = {}

        colors = {0: "#ff4757", 1: "#2ed573", 2: "#1e90ff", 3: "#ffa502", 4: "#a4b0be"}
        max_score = max(importance_scores.values()) if importance_scores and len(importance_scores) > 0 else 1.0

        for idx in top_node_indices:
            if idx >= len(games):
                continue
            g = games[idx]
            title = g["title"]
            tier = g["cluster_id"]
            color = colors.get(tier, "#1e90ff")
            pos_v = g["numerical_metrics"]["positive_votes"]
            neg_v = g["numerical_metrics"]["negative_votes"]
            pol = g["numerical_metrics"]["community_polarity_score"]
            score = importance_scores.get(idx, 0.0)
            
            size = int(14 + (score / (max_score if max_score > 0 else 1.0)) * 22)
            label_text = f"{title}\n(Tier {tier})"
            tooltip = f"Jogo: {title} | Tier: {tier} | Polaridade: {pol:.2f} | Votos: +{pos_v} / -{neg_v}"
            
            nodes_list.append({
                "id": idx,
                "label": label_text,
                "title": tooltip,
                "color": color,
                "size": size,
                "shadow": True
            })

            visual_freq_map[str(idx)] = {
                "title": title,
                "steam_appid": g.get("steam_appid"),
                "cluster_id": tier,
                "metrics": g["numerical_metrics"],
                "review_word_frequencies": frequency_database.get(title, {}).get("review_word_frequencies", {})
            }

        for u, v, data in G.edges(data=True):
            if u in top_node_indices and v in top_node_indices:
                weight = data.get("weight", 0.5)
                width = max(1, int(weight * 3))
                edges_list.append({
                    "from": u,
                    "to": v,
                    "width": width,
                    "color": {"color": "#a4b0be", "opacity": 0.55}
                })

        nodes_json_str = json.dumps(nodes_list, ensure_ascii=False)
        edges_json_str = json.dumps(edges_list, ensure_ascii=False)
        freq_json_str = json.dumps(visual_freq_map, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Rede de Inteligência de Mercado - Top {len(nodes_list)} Hubs & Frequência de Reviews</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f5f6fa; margin: 0; padding: 20px; color: #2f3640; }}
        h1 {{ margin-top: 0; }}
        .main-layout {{ display: flex; gap: 20px; align-items: flex-start; }}
        #network-container {{ flex: 2; height: 720px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        #json-panel {{ flex: 1; height: 720px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 16px; box-sizing: border-box; overflow-y: auto; }}
        .legend {{ margin-top: 15px; padding: 12px; background: #fff; border-radius: 5px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .badge {{ display: inline-block; width: 14px; height: 14px; margin-right: 6px; vertical-align: middle; border-radius: 3px; }}
        .kw-tag {{ display: inline-block; padding: 4px 8px; margin: 3px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .kw-pos {{ background-color: #dff9fb; color: #0984e3; border: 1px solid #74b9ff; }}
        .kw-neg {{ background-color: #ffeaa7; color: #d63031; border: 1px solid #fab1a0; }}
        pre {{ background: #2f3640; color: #f5f6fa; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; }}
        .status-pill {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; background: #2ed573; color: #fff; font-weight: bold; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>Rede de Inteligência de Mercado - Top {len(nodes_list)} Hubs & Frequência de Reviews</h1>
    <p>Física estabilizada automaticamente (arestas travadas). <strong>Clique em qualquer nó</strong> para inspecionar o JSON de frequência de palavras.</p>
    
    <div class="main-layout">
        <div id="network-container"></div>
        <div id="json-panel">
            <span id="physics-status" class="status-pill">Estabilizando layout...</span>
            <h3>Inspetor de Frequência (frequencia_reviews.json)</h3>
            <div id="review-details">
                <p style="color: #7f8fa6;">Selecione um jogo no grafo ao lado para visualizar as palavras-chave positivas, negativas e o objeto JSON completo.</p>
            </div>
        </div>
    </div>
    
    <div class="legend">
        <strong>Legenda de Tiers:</strong><br>
        <span class="badge" style="background: #ff4757;"></span> Tier 0 (Hub Principal / Sim-Racing & Âncoras) &nbsp;&nbsp;
        <span class="badge" style="background: #2ed573;"></span> Tier 1 (Consagrado Positivo) &nbsp;&nbsp;
        <span class="badge" style="background: #1e90ff;"></span> Tier 2 (Equilibrado) &nbsp;&nbsp;
        <span class="badge" style="background: #ffa502;"></span> Tier 3 (Baixo Volume)
    </div>

    <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json_str});
        var edges = new vis.DataSet({edges_json_str});
        var reviewFreqDB = {freq_json_str};

        var container = document.getElementById('network-container');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            nodes: {{ shape: 'box', font: {{ color: '#fff', face: 'Arial', size: 12 }}, borderRadius: 6, padding: 8 }},
            edges: {{ smooth: false }},
            physics: {{
                enabled: true,
                barnesHut: {{ gravitationalConstant: -4000, centralGravity: 0.35, springLength: 140, damping: 0.3 }},
                stabilization: {{ enabled: true, iterations: 200, updateInterval: 25 }}
            }},
            interaction: {{ dragNodes: true, hover: true }}
        }};

        var network = new vis.Network(container, data, options);

        network.on("stabilizationIterationsDone", function () {{
            network.setOptions({{ physics: false }});
            var badge = document.getElementById('physics-status');
            badge.textContent = "Física travada (layout estático)";
            badge.style.background = "#1e90ff";
        }});

        network.on("click", function (params) {{
            if (params.nodes.length > 0) {{
                var nodeId = String(params.nodes[0]);
                var item = reviewFreqDB[nodeId];
                if (!item) return;

                var posList = (item.review_word_frequencies.positive_top_keywords || [])
                    .map(k => '<span class="kw-tag kw-pos">' + k.word + ' (' + k.frequency + ')</span>').join('') || '<em>Nenhuma palavra positiva encontrada</em>';
                var negList = (item.review_word_frequencies.negative_top_keywords || [])
                    .map(k => '<span class="kw-tag kw-neg">' + k.word + ' (' + k.frequency + ')</span>').join('') || '<em>Nenhuma palavra negativa encontrada</em>';

                document.getElementById('review-details').innerHTML =
                    '<h4>' + item.title + ' (Tier ' + item.cluster_id + ')</h4>' +
                    '<p><strong>Votos:</strong> +' + item.metrics.positive_votes + ' / -' + item.metrics.negative_votes + '</p>' +
                    '<p><strong>Palavras Positivas:</strong><br>' + posList + '</p>' +
                    '<p><strong>Palavras Negativas:</strong><br>' + negList + '</p>' +
                    '<p><strong>Objeto JSON:</strong></p>' +
                    '<pre>' + JSON.stringify(item.review_word_frequencies, null, 2) + '</pre>';
            }}
        }});
    </script>
</body>
</html>
"""
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def run_pipeline(self):
        total_start_time = time.time()
        print("[Início] Executando pipeline de Inteligência de Mercado com Pandas...", flush=True)
        
        games = self.load_and_merge_databases(target_count=self.target_count)
        if not games:
            print("[ERRO] Nenhum jogo carregado no pool.", flush=True)
            return

        print("[3/5] Normalizando métricas e construindo grafo de similaridade...", flush=True)
        processed_games = []
        genre_buckets = defaultdict(list)

        for idx, g in enumerate(games):
            metrics = g.get("numerical_metrics", {})
            genres_raw = g.get("genres_string", "")
            title = g.get("title", "")
            
            genre_list = [genre.strip().lower() for genre in genres_raw.split(",") if genre.strip() and genre.strip().lower() != "unknown"]
            primary_genre = genre_list[0] if genre_list else "unknown"
            genres_set = set(genre_list)

            is_sim_racing = (
                ("racing" in genres_set or "simulation" in genres_set) and 
                any(kw in title.lower() for kw in ["iracing", "assetto", "factor", "automobilista", "sim", "rally"])
            ) or ("iracing" in title.lower())

            if "iracing" in title.lower():
                primary_genre = "simulation"

            rating = metrics.get("igdb_rating_raw", 70.0)
            polarity = metrics.get("community_polarity_score", 0.5)
            total_votes = metrics.get("total_votes", 0)
            players = math.log1p(metrics.get("current_steam_players_raw", 0))
            volume_weight = math.log1p(total_votes)

            processed_games.append({
                "original_index": idx,
                "original_data": g,
                "title": title,
                "primary_genre": primary_genre,
                "genres_set": genres_set,
                "is_sim_racing": is_sim_racing,
                "rating": rating,
                "polarity": polarity,
                "total_votes": total_votes,
                "volume_weight": volume_weight,
                "players": players
            })
            genre_buckets[primary_genre].append(idx)

        G = nx.Graph()
        for idx in range(len(processed_games)):
            G.add_node(idx)

        def calc_sim(ga, gb):
            g_a, g_b = ga["genres_set"], gb["genres_set"]
            genre_sim = len(g_a.intersection(g_b)) / len(g_a.union(g_b)) if (g_a or g_b) else 0.0
            r_sim = 1.0 - (abs(ga["rating"] - gb["rating"]) / 100.0)
            p_sim = max(0.0, 1.0 - (abs(ga["players"] - gb["players"]) / 15.0))
            pol_sim = 1.0 - abs(ga["polarity"] - gb["polarity"])
            vol_sim = max(0.0, 1.0 - (abs(ga["volume_weight"] - gb["volume_weight"]) / 12.0))

            if ga["is_sim_racing"] and gb["is_sim_racing"]:
                w = [0.15, 0.10, 0.25, 0.25, 0.25]
            else:
                w = [0.30, 0.15, 0.15, 0.20, 0.20]

            return (genre_sim * w[0] + r_sim * w[1] + p_sim * w[2] + pol_sim * w[3] + vol_sim * w[4]) / sum(w)

        print("Calculando arestas do grafo com cronômetro...", flush=True)
        bucket_keys = list(genre_buckets.keys())
        compared_pairs = set()
        start_graph = time.time()

        for b_idx, genre in enumerate(bucket_keys, start=1):
            indices = genre_buckets[genre]
            b_len = len(indices)
            for i in range(b_len):
                idx_a = indices[i]
                for j in range(i + 1, b_len):
                    idx_b = indices[j]
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    if pair in compared_pairs:
                        continue
                    compared_pairs.add(pair)
                    
                    sim = calc_sim(processed_games[idx_a], processed_games[idx_b])
                    if sim >= 0.65:
                        G.add_edge(idx_a, idx_b, weight=sim, distance=max(0.01, 1.0 - sim))

            elapsed = time.time() - start_graph
            print(f"[Grafo] Gênero {b_idx}/{len(bucket_keys)} ({genre}) | Arestas: {G.number_of_edges()} | Tempo: {elapsed:.1f}s", end="\r", flush=True)

        print(f"\n[4/5] Executando Dijkstra e calculando centralidade ponderada por volume...", flush=True)
        anchor_nodes = []
        for genre, indices in genre_buckets.items():
            best_idx = max(
                indices, 
                key=lambda i: (processed_games[i]["rating"] * 0.3) + 
                              (processed_games[i]["volume_weight"] * 10.0) + 
                              (processed_games[i]["players"] * 3.0)
            )
            anchor_nodes.append(best_idx)

        importance_scores = defaultdict(float)
        start_dijkstra = time.time()
        for a_idx, anchor in enumerate(anchor_nodes, start=1):
            if anchor in G:
                try:
                    _, paths = nx.single_source_dijkstra(G, source=anchor, weight='distance')
                    for target, path in paths.items():
                        plen = len(path)
                        for node in path:
                            vol_factor = max(0.1, processed_games[node]["volume_weight"])
                            importance_scores[node] += (1.0 / plen) * vol_factor
                except nx.NetworkXNoPath:
                    pass
            elapsed_d = time.time() - start_dijkstra
            print(f"[Dijkstra] Âncora {a_idx}/{len(anchor_nodes)} | Tempo: {elapsed_d:.1f}s", end="\r", flush=True)

        print(f"\n[5/5] Classificando Tiers (0 a 4) e gerando relatórios...", flush=True)
        sorted_nodes = sorted(G.nodes(), key=lambda n: importance_scores.get(n, 0), reverse=True)
        tier_size = max(1, len(processed_games) // 5)

        coloring = {}
        for rank, node_idx in enumerate(sorted_nodes):
            game_info = processed_games[node_idx]
            total_v = game_info["total_votes"]
            pol = game_info["polarity"]

            if total_v < 100:
                coloring[node_idx] = 4
            elif total_v < 500:
                coloring[node_idx] = 3
            elif total_v < 2000:
                coloring[node_idx] = 2
            elif game_info["is_sim_racing"] and pol >= 0.70 and rank < (tier_size * 2):
                coloring[node_idx] = 0
            else:
                raw_tier = min(4, rank // tier_size)
                if raw_tier == 0 and (pol < 0.75 or total_v < 5000):
                    coloring[node_idx] = 1 if pol >= 0.65 else 2
                else:
                    coloring[node_idx] = raw_tier

        tier_analytics = defaultdict(lambda: {"games_count": 0, "avg_igdb_rating": 0.0, "avg_community_polarity": 0.0})
        
        output_database = []
        frequency_database = {}

        for idx, item in enumerate(processed_games):
            orig = item["original_data"]
            tier = coloring.get(idx, 4)
            orig["cluster_id"] = tier
            output_database.append(orig)

            frequency_database[orig["title"]] = {
                "steam_appid": orig.get("steam_appid"),
                "cluster_id": tier,
                "review_word_frequencies": orig.get("review_word_frequencies", {})
            }

            t_stat = tier_analytics[tier]
            t_stat["games_count"] += 1
            t_stat["avg_igdb_rating"] += orig["numerical_metrics"]["igdb_rating_raw"]
            t_stat["avg_community_polarity"] += orig["numerical_metrics"]["community_polarity_score"]

        for tier, stats in tier_analytics.items():
            count = stats["games_count"]
            if count > 0:
                stats["avg_igdb_rating"] = round(stats["avg_igdb_rating"] / count, 2)
                stats["avg_community_polarity"] = round(stats["avg_community_polarity"] / count, 4)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_database, f, indent=4, ensure_ascii=False)

        with open(self.freq_output_path, 'w', encoding='utf-8') as f:
            json.dump(frequency_database, f, indent=4, ensure_ascii=False)

        print("\nGerando visualizador HTML interativo...", flush=True)
        self.generate_html_visualization(output_database, G, importance_scores, frequency_database)

        total_elapsed = time.time() - total_start_time

        print("\n" + "="*70, flush=True)
        print(f" RELATÓRIO DE INTELIGÊNCIA DE MERCADO", flush=True)
        print(f" Tempo Total de Compilação: {total_elapsed:.2f} segundos", flush=True)
        print("="*70, flush=True)
        for tier in sorted(tier_analytics.keys()):
            s = tier_analytics[tier]
            print(f"[Tier Estrutural {tier}] Jogos: {s['games_count']} | Média IGDB: {s['avg_igdb_rating']} | Polaridade: {s['avg_community_polarity']:.2f}", flush=True)
        print("="*70, flush=True)
        print(f"[SUCESSO TOTAL] Arquivos gerados com sucesso:\n -> {self.output_path}\n -> {self.freq_output_path}\n -> {self.html_path}", flush=True)

if __name__ == "__main__":
    pipeline = MarketIntelligencePipeline(target_count=500, top_n_visual=150)
    pipeline.run_pipeline()