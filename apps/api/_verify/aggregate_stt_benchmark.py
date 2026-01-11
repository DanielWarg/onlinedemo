#!/usr/bin/env python3
"""
Aggregera alla STT benchmark-resultat till en sammanfattning och skapa markdown-rapport.
"""
import json
from pathlib import Path

def load_all_results(results_dir: Path):
    """Load all benchmark results."""
    master_file = results_dir / "stt_benchmark_report.json"
    if not master_file.exists():
        return None
    
    with open(master_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_markdown_report(data: dict, output_file: Path):
    """Generate markdown report from aggregated data."""
    if not data or 'configurations' not in data:
        return
    
    configs = data['configurations']
    
    # Build table
    rows = []
    for config_key, config_data in sorted(configs.items()):
        engine = config_data['config']['engine']
        model = config_data['config']['model']
        runs = config_data['runs']
        
        if len(runs) == 0:
            continue
        
        # Get averages
        avg = config_data.get('averages', {})
        run1 = runs[0] if len(runs) > 0 else {}
        run2 = runs[1] if len(runs) > 1 else run1
        
        quality = run1.get('quality', {})
        
        rows.append({
            'engine': engine,
            'model': model,
            'run1_time': run1.get('transcribe_time_s', 0),
            'run2_time': run2.get('transcribe_time_s', 0),
            'avg_time': avg.get('transcribe_time_s', 0),
            'cpu_peak': avg.get('cpu_peak_pct', 0),
            'cpu_avg': avg.get('cpu_avg_pct', 0),
            'ram_peak': avg.get('ram_peak_gb', 0),
            'word_count': quality.get('word_count', 0),
            'nonsense_ratio': quality.get('nonsense_ratio', 0),
            'swedish_ratio': quality.get('swedish_chars_ratio', 0),
            'snippets': run1.get('snippets', {}),
            'enhanced_snippets': run1.get('enhanced_snippets', {})
        })
    
    # Generate markdown
    md = "# STT Benchmark Matrix - Prestanda & Kvalitet\n\n"
    md += "## Översikt\n\n"
    md += "Jämförelse mellan Whisper och faster-whisper med base/small modeller.\n\n"
    md += "## Resultat\n\n"
    
    # Table
    md += "| Engine | Model | Run 1 (s) | Run 2 (s) | Avg (s) | CPU Peak (%) | CPU Avg (%) | RAM Peak (GB) | Word Count | Nonsense Ratio | Swedish Chars |\n"
    md += "|--------|-------|-----------|-----------|---------|--------------|-------------|---------------|------------|----------------|---------------|\n"
    
    for row in rows:
        md += f"| {row['engine']} | {row['model']} | {row['run1_time']:.1f} | {row['run2_time']:.1f} | {row['avg_time']:.1f} | "
        md += f"{row['cpu_peak']:.1f} | {row['cpu_avg']:.1f} | {row['ram_peak']:.2f} | "
        md += f"{row['word_count']} | {row['nonsense_ratio']:.3f} | {row['swedish_ratio']:.3f} |\n"
    
    md += "\n## Kvalitetsjämförelse (Snippets)\n\n"
    
    for row in rows:
        md += f"### {row['engine']} {row['model']}\n\n"
        
        snippets = row.get('snippets', {})
        enhanced = row.get('enhanced_snippets', {})
        
        md += "**Början:**\n"
        md += f"- Raw: {snippets.get('beginning', 'N/A')[:200]}...\n"
        md += f"- Enhanced: {enhanced.get('beginning', 'N/A')[:200]}...\n\n"
        
        md += "**Mitten:**\n"
        md += f"- Raw: {snippets.get('middle', 'N/A')[:200]}...\n"
        md += f"- Enhanced: {enhanced.get('middle', 'N/A')[:200]}...\n\n"
        
        md += "**Slut:**\n"
        md += f"- Raw: {snippets.get('end', 'N/A')[:200]}...\n"
        md += f"- Enhanced: {enhanced.get('end', 'N/A')[:200]}...\n\n"
    
    md += "\n## Rekommendation\n\n"
    
    # Find sweetspot (best balance of speed and quality)
    best_speed = min(rows, key=lambda x: x['avg_time'])
    best_quality = max(rows, key=lambda x: x['word_count'] - x['nonsense_ratio'] * 1000)
    
    md += f"### Snabbast: {best_speed['engine']} {best_speed['model']}\n"
    md += f"- Tid: {best_speed['avg_time']:.1f}s\n"
    md += f"- CPU Peak: {best_speed['cpu_peak']:.1f}%\n"
    md += f"- RAM: {best_speed['ram_peak']:.2f}GB\n\n"
    
    md += f"### Bäst kvalitet: {best_quality['engine']} {best_quality['model']}\n"
    md += f"- Word Count: {best_quality['word_count']}\n"
    md += f"- Nonsense Ratio: {best_quality['nonsense_ratio']:.3f}\n"
    md += f"- Swedish Chars: {best_quality['swedish_ratio']:.3f}\n\n"
    
    # Sweetspot: balance between speed and quality
    # Score = (1/time) * quality_score
    scored = []
    for row in rows:
        if row['avg_time'] > 0:
            speed_score = 100 / row['avg_time']  # Higher is better
            quality_score = row['word_count'] * (1 - row['nonsense_ratio']) * (1 + row['swedish_ratio'])
            combined_score = speed_score * quality_score
            scored.append((row, combined_score))
    
    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        sweetspot = scored[0][0]
        
        md += f"### Sweetspot (Rekommendation): {sweetspot['engine']} {sweetspot['model']}\n\n"
        md += f"**Anledning:**\n"
        md += f"- Balanserar hastighet ({sweetspot['avg_time']:.1f}s) och kvalitet ({sweetspot['word_count']} ord, {sweetspot['nonsense_ratio']:.3f} nonsense ratio)\n"
        md += f"- CPU-användning: {sweetspot['cpu_peak']:.1f}% peak, {sweetspot['cpu_avg']:.1f}% medel\n"
        md += f"- Minne: {sweetspot['ram_peak']:.2f}GB\n"
        md += f"- Lämplig för demo: Acceptabel hastighet med bra kvalitet\n\n"
    
    md += "---\n\n"
    md += "*Genererad automatiskt från benchmark-resultat*\n"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"✅ Markdown-rapport skapad: {output_file}")

def main():
    results_dir = Path("/app/test_results")
    results_dir.mkdir(exist_ok=True)
    
    data = load_all_results(results_dir)
    if not data:
        print("❌ Inga benchmark-resultat hittades")
        return 1
    
    # Save to test_results (will be copied to docs/ by Makefile)
    output_file = results_dir / "STT_BENCHMARK.md"
    
    generate_markdown_report(data, output_file)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

