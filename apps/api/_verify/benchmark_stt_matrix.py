#!/usr/bin/env python3
"""
STT Benchmark Matrix: Jämför Whisper vs faster-whisper med base/small modeller.

Kör 2 repetitioner per konfiguration och mäter:
- Transkriberingstid
- CPU peak/avg
- RAM peak
- Kvalitetsmetrics (word count, nonsense ratio, svenska tecken)
- Snippets (början/mitt/slut) för jämförelse

Output:
- JSON rapport: test_results/stt_benchmark_report.json
- Transcripts: test_results/transcripts/{engine}_{model}_run{n}.txt
"""
import sys
import os
import json
import time
import re
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil inte tillgängligt - CPU/RAM metrics kommer vara begränsade")

def get_process_metrics() -> Dict:
    """Get current process CPU and memory metrics."""
    if PSUTIL_AVAILABLE:
        process = psutil.Process(os.getpid())
        return {
            'cpu_percent': process.cpu_percent(interval=0.1),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'num_threads': process.num_threads()
        }
    else:
        # Fallback: read from /proc/self/status
        try:
            with open('/proc/self/status', 'r') as f:
                status = f.read()
                vmrss_match = re.search(r'VmRSS:\s+(\d+)\s+kB', status)
                if vmrss_match:
                    memory_mb = int(vmrss_match.group(1)) / 1024
                else:
                    memory_mb = 0
            return {
                'cpu_percent': 0,  # Can't measure without psutil
                'memory_mb': memory_mb,
                'num_threads': 0
            }
        except:
            return {'cpu_percent': 0, 'memory_mb': 0, 'num_threads': 0}

def monitor_metrics_during_run(duration: float, interval: float = 0.5) -> Tuple[List[Dict], threading.Thread]:
    """Monitor CPU/RAM during a run in background thread."""
    import threading
    metrics = []
    start_time = time.time()
    stop_event = threading.Event()
    
    def monitor():
        while not stop_event.is_set() and (time.time() - start_time) < duration + 5:
            m = get_process_metrics()
            m['timestamp'] = time.time() - start_time
            metrics.append(m)
            time.sleep(interval)
    
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    return metrics, thread, stop_event

def transcribe_with_whisper(audio_path: str, model_name: str, show_progress: bool = True) -> str:
    """Transcribe using openai-whisper."""
    import whisper
    from tqdm import tqdm
    
    if show_progress:
        print(f"    📥 Laddar modell '{model_name}'...", flush=True)
    
    model = whisper.load_model(model_name)
    
    if show_progress:
        print(f"    🎤 Transkriberar audio...", flush=True)
    
    # Whisper doesn't have built-in progress, but we can show a spinner
    result = model.transcribe(audio_path, language=None, task="transcribe")  # Auto-detect language
    return result["text"].strip()

def transcribe_with_faster_whisper(audio_path: str, model_name: str, show_progress: bool = True) -> str:
    """Transcribe using faster-whisper."""
    from faster_whisper import WhisperModel
    
    if show_progress:
        print(f"    📥 Laddar modell '{model_name}'...", flush=True)
    
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    
    if show_progress:
        print(f"    🎤 Transkriberar audio (detta kan ta flera minuter)...", flush=True)
    
    segments, info = model.transcribe(audio_path, language=None)  # Auto-detect language
    
    # Collect segments (faster-whisper returns iterator)
    transcript_parts = []
    segment_count = 0
    for segment in segments:
        transcript_parts.append(segment.text)
        segment_count += 1
        if show_progress and segment_count % 10 == 0:
            print(f"    📝 Processerat {segment_count} segment...", flush=True)
    
    if show_progress:
        print(f"    ✅ Totalt {segment_count} segment processerade", flush=True)
    
    transcript = " ".join(transcript_parts)
    return transcript.strip()

def analyze_quality(transcript: str) -> Dict:
    """Analyze transcript quality with simple heuristics."""
    if not transcript:
        return {
            'word_count': 0,
            'unique_word_ratio': 0,
            'nonsense_ratio': 0,
            'swedish_chars_ratio': 0
        }
    
    words = transcript.split()
    word_count = len(words)
    
    # Unique word ratio
    unique_words = len(set(words))
    unique_ratio = unique_words / word_count if word_count > 0 else 0
    
    # Nonsense ratio: words with 3+ consecutive consonants or many special chars
    nonsense_count = 0
    for word in words:
        # Check for 3+ consecutive consonants (simple heuristic)
        consonants = re.sub(r'[aeiouyåäöAEIOUYÅÄÖ\s]', '', word)
        if len(consonants) >= 3 and len(word) <= 5:
            nonsense_count += 1
        # Check for excessive special chars
        special_chars = len(re.findall(r'[^a-zA-ZåäöÅÄÖ0-9\s]', word))
        if special_chars > len(word) * 0.3:
            nonsense_count += 1
    
    nonsense_ratio = nonsense_count / word_count if word_count > 0 else 0
    
    # Swedish chars ratio
    swedish_chars = len(re.findall(r'[åäöÅÄÖ]', transcript))
    total_chars = len(re.findall(r'[a-zA-ZåäöÅÄÖ]', transcript))
    swedish_ratio = swedish_chars / total_chars if total_chars > 0 else 0
    
    return {
        'word_count': word_count,
        'unique_word_ratio': unique_ratio,
        'nonsense_ratio': nonsense_ratio,
        'swedish_chars_ratio': swedish_ratio
    }

def extract_snippets(transcript: str, num_snippets: int = 3) -> List[str]:
    """Extract snippets from beginning, middle, and end."""
    sentences = re.split(r'[.!?]+\s+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) == 0:
        return ["(tom transkript)"]
    
    snippets = []
    if len(sentences) >= num_snippets:
        # Beginning
        snippets.append(". ".join(sentences[:2]) + ".")
        # Middle
        mid_start = len(sentences) // 2
        snippets.append(". ".join(sentences[mid_start:mid_start+2]) + ".")
        # End
        snippets.append(". ".join(sentences[-2:]) + ".")
    else:
        # Use all sentences
        snippets.append(". ".join(sentences) + ".")
        while len(snippets) < num_snippets:
            snippets.append("(för få meningar)")
    
    return snippets

def run_benchmark(audio_path: str, engine: str, model: str, run_number: int) -> Dict:
    """Run a single benchmark iteration."""
    print(f"  ⏱️  Run {run_number}: {engine} {model}...", flush=True)
    
    # Start monitoring
    monitor_metrics, monitor_thread, stop_event = monitor_metrics_during_run(duration=600, interval=1.0)
    
    # Run transcription
    start_time = time.perf_counter()
    transcript = None
    try:
        if engine == "whisper":
            transcript = transcribe_with_whisper(audio_path, model, show_progress=True)
        elif engine == "faster_whisper":
            transcript = transcribe_with_faster_whisper(audio_path, model, show_progress=True)
        else:
            raise ValueError(f"Unknown engine: {engine}")
        
        transcribe_time = time.perf_counter() - start_time
    except Exception as e:
        stop_event.set()
        monitor_thread.join(timeout=2)
        print(f" FAILED: {str(e)}")
        return {
            'error': str(e),
            'transcribe_time_s': 0,
            'transcript': ""
        }
    finally:
        stop_event.set()
        monitor_thread.join(timeout=2)
    
    if not transcript:
        return {
            'error': 'No transcript returned',
            'transcribe_time_s': 0,
            'transcript': ""
        }
    
    # Calculate metrics from monitoring
    if monitor_metrics:
        cpu_values = [m['cpu_percent'] for m in monitor_metrics if m['cpu_percent'] > 0]
        ram_values = [m['memory_mb'] for m in monitor_metrics]
        
        cpu_peak = max(cpu_values) if cpu_values else 0
        cpu_avg = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        ram_peak_gb = (max(ram_values) / 1024) if ram_values else 0
    else:
        cpu_peak = 0
        cpu_avg = 0
        ram_peak_gb = 0
    
    # Quality analysis
    quality = analyze_quality(transcript)
    snippets = extract_snippets(transcript, num_snippets=3)
    
    # Apply enhanced normalization to snippets
    try:
        from text_processing import normalize_transcript_text
        enhanced_snippets = [normalize_transcript_text(s) for s in snippets]
    except:
        enhanced_snippets = snippets
    
    result = {
        'run_number': run_number,
        'engine': engine,
        'model': model,
        'transcribe_time_s': round(transcribe_time, 2),
        'cpu_peak_pct': round(cpu_peak, 1),
        'cpu_avg_pct': round(cpu_avg, 1),
        'ram_peak_gb': round(ram_peak_gb, 2),
        'quality': quality,
        'snippets': {
            'beginning': snippets[0] if len(snippets) > 0 else "",
            'middle': snippets[1] if len(snippets) > 1 else "",
            'end': snippets[2] if len(snippets) > 2 else ""
        },
        'enhanced_snippets': {
            'beginning': enhanced_snippets[0] if len(enhanced_snippets) > 0 else "",
            'middle': enhanced_snippets[1] if len(enhanced_snippets) > 1 else "",
            'end': enhanced_snippets[2] if len(enhanced_snippets) > 2 else ""
        },
        'transcript': transcript  # Save full transcript for file output
    }
    
    print(f"  ✅ Transkribering klar: {transcribe_time:.1f}s")
    print(f"  📊 CPU peak: {cpu_peak:.1f}%, RAM peak: {ram_peak_gb:.2f}GB")
    print(f"  📝 Ord: {quality.get('word_count', 0)}, Nonsense: {quality.get('nonsense_ratio', 0):.3f}")
    
    return result

def main():
    """Run benchmark matrix."""
    from tqdm import tqdm
    
    # Get config from env
    engine = os.getenv("STT_ENGINE", "whisper")
    model = os.getenv("WHISPER_MODEL", "base")
    audio_path = os.getenv("TEST_AUDIO_PATH", "/app/Del21.wav")
    num_runs = int(os.getenv("NUM_RUNS", "2"))
    
    print("=" * 70)
    print("STT BENCHMARK MATRIX")
    print("=" * 70)
    print(f"Engine: {engine}")
    print(f"Model: {model}")
    print(f"Audio: {audio_path}")
    print(f"Runs: {num_runs}")
    print()
    
    # Check audio file exists
    if not Path(audio_path).exists():
        print(f"❌ Audio file not found: {audio_path}")
        return 1
    
    file_size_mb = Path(audio_path).stat().st_size / 1024 / 1024
    print(f"File size: {file_size_mb:.2f} MB")
    print()
    
    # Create output directories
    results_dir = Path("/app/test_results")
    transcripts_dir = results_dir / "transcripts"
    results_dir.mkdir(exist_ok=True)
    transcripts_dir.mkdir(exist_ok=True)
    
    # Run benchmarks with progress
    all_results = []
    print(f"🚀 Startar {num_runs} körningar...")
    print()
    
    for run_num in range(1, num_runs + 1):
        print(f"\n{'='*70}")
        print(f"KÖRNING {run_num}/{num_runs}: {engine} {model}")
        print(f"{'='*70}")
        
        result = run_benchmark(audio_path, engine, model, run_num)
        if 'error' in result:
            print(f"❌ Run {run_num} failed: {result.get('error', 'Unknown error')}")
            continue
        
        all_results.append(result)
        print(f"✅ Run {run_num} klar!")
        print()
        
        # Save transcript
        transcript_file = transcripts_dir / f"{engine}_{model}_run{run_num}.txt"
        try:
            transcript_text = result.get('transcript', '')
            if transcript_text:
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(transcript_text)
        except Exception as e:
            print(f"⚠️  Could not save transcript: {str(e)}")
        
        print()
    
    # Calculate averages
    if len(all_results) >= 2:
        avg_time = sum(r['transcribe_time_s'] for r in all_results) / len(all_results)
        avg_cpu_peak = sum(r['cpu_peak_pct'] for r in all_results) / len(all_results)
        avg_cpu_avg = sum(r['cpu_avg_pct'] for r in all_results) / len(all_results)
        avg_ram_peak = sum(r['ram_peak_gb'] for r in all_results) / len(all_results)
    else:
        avg_time = all_results[0]['transcribe_time_s'] if all_results else 0
        avg_cpu_peak = all_results[0]['cpu_peak_pct'] if all_results else 0
        avg_cpu_avg = all_results[0]['cpu_avg_pct'] if all_results else 0
        avg_ram_peak = all_results[0]['ram_peak_gb'] if all_results else 0
    
    # Create report
    report = {
        'config': {
            'engine': engine,
            'model': model,
            'audio_file': audio_path,
            'file_size_mb': round(file_size_mb, 2),
            'num_runs': num_runs
        },
        'runs': all_results,
        'averages': {
            'transcribe_time_s': round(avg_time, 2),
            'cpu_peak_pct': round(avg_cpu_peak, 1),
            'cpu_avg_pct': round(avg_cpu_avg, 1),
            'ram_peak_gb': round(avg_ram_peak, 2)
        }
    }
    
    # Save report (per-configuration)
    config_key = f"{engine}_{model}"
    report_file = results_dir / f"stt_benchmark_{config_key}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Also append to master report
    master_report_file = results_dir / "stt_benchmark_report.json"
    master_data = {}
    if master_report_file.exists():
        try:
            with open(master_report_file, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
        except:
            master_data = {}
    
    if 'configurations' not in master_data:
        master_data['configurations'] = {}
    master_data['configurations'][config_key] = report
    
    with open(master_report_file, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)
    
    print("=" * 70)
    print("SAMMANFATTNING")
    print("=" * 70)
    print(f"Runs completed: {len(all_results)}/{num_runs}")
    if all_results:
        print(f"Avg time: {avg_time:.1f}s")
        print(f"Avg CPU peak: {avg_cpu_peak:.1f}%")
        print(f"Avg RAM peak: {avg_ram_peak:.2f}GB")
    print(f"Report saved: {report_file}")
    print()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Avbruten av användare")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FEL: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

