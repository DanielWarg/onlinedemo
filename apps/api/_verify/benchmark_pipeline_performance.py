#!/usr/bin/env python3
"""
Funktionstest: Mät pipeline-prestanda och identifiera flaskhalsar.

Mäter:
1. Import-tider (text_processing, whisper)
2. Modellladdning (Whisper)
3. Transkribering (Whisper)
4. Normalisering (normalize_transcript_text)
5. Processering (process_transcript)
6. Refinering (refine_editorial_text)
7. Maskering (mask_text)
8. PII gate check (pii_gate_check)

Rapporterar detaljerad timing för varje steg.
"""
import sys
import time
import os
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def get_process_info() -> Dict:
    """Get current process CPU and memory info."""
    process = psutil.Process(os.getpid())
    return {
        'cpu_percent': process.cpu_percent(interval=0.1),
        'memory_mb': process.memory_info().rss / 1024 / 1024,
        'num_threads': process.num_threads()
    }

def monitor_cpu(interval: float = 0.5, duration: float = 10.0) -> List[Dict]:
    """Monitor CPU usage in background thread."""
    results = []
    start_time = time.time()
    
    def monitor():
        process = psutil.Process(os.getpid())
        while time.time() - start_time < duration:
            results.append({
                'time': time.time() - start_time,
                'cpu_percent': process.cpu_percent(interval=interval),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'num_threads': process.num_threads()
            })
            time.sleep(interval)
    
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    return results, thread

def benchmark_step(step_name: str, func, *args, **kwargs) -> Tuple[float, any]:
    """Benchmark a single step and return (time, result)."""
    print(f"  ⏱️  {step_name}...", end="", flush=True)
    start_time = time.time()
    start_info = get_process_info()
    
    try:
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        end_info = get_process_info()
        
        print(f" {elapsed:.2f}s")
        print(f"     CPU: {end_info['cpu_percent']:.1f}%, Memory: {end_info['memory_mb']:.1f}MB, Threads: {end_info['num_threads']}")
        
        return elapsed, result
    except Exception as e:
        elapsed = time.time() - start_time
        print(f" FAILED ({elapsed:.2f}s): {str(e)}")
        raise

def main():
    """Run comprehensive pipeline benchmark."""
    print("=" * 70)
    print("PIPELINE PRESTANDATEST - Identifiera Flaskhalsar")
    print("=" * 70)
    print()
    
    # Test file
    test_audio = Path(__file__).parent.parent / "Del21.wav"
    if not test_audio.exists():
        print(f"❌ Testfil hittades inte: {test_audio}")
        print("   Använder en mindre testfil eller skapar stub...")
        # Create a small test file or use existing
        return 1
    
    file_size_mb = test_audio.stat().st_size / 1024 / 1024
    print(f"Testfil: {test_audio.name}")
    print(f"Storlek: {file_size_mb:.2f} MB")
    print()
    
    results = {}
    
    # STEP 1: Import text_processing (utan whisper)
    print("STEG 1: Import text_processing (utan whisper)")
    print("-" * 70)
    elapsed, _ = benchmark_step(
        "Import text_processing",
        lambda: __import__('text_processing', fromlist=['normalize_text'])
    )
    results['import_text_processing'] = elapsed
    print()
    
    # STEP 2: Import whisper
    print("STEG 2: Import whisper")
    print("-" * 70)
    elapsed, _ = benchmark_step(
        "Import whisper",
        lambda: __import__('whisper')
    )
    results['import_whisper'] = elapsed
    print()
    
    # STEP 3: Ladda Whisper-modell
    print("STEG 3: Ladda Whisper-modell")
    print("-" * 70)
    from text_processing import _get_whisper_model
    elapsed, model = benchmark_step(
        "Ladda Whisper model (medium)",
        _get_whisper_model
    )
    results['load_model'] = elapsed
    model_size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024 / 1024 if hasattr(model, 'parameters') else 0
    print(f"     Modellstorlek: ~{model_size_mb:.1f}MB (uppskattning)")
    print()
    
    # STEP 4: Transkribering
    print("STEG 4: Transkribering (Whisper)")
    print("-" * 70)
    from text_processing import transcribe_audio
    
    # Start CPU monitoring
    print("  📊 Startar CPU-monitorering...")
    monitor_results, monitor_thread = monitor_cpu(interval=1.0, duration=300)  # Max 5 min
    
    elapsed, raw_transcript = benchmark_step(
        "Transkribera audio (Whisper)",
        transcribe_audio,
        str(test_audio)
    )
    results['transcribe'] = elapsed
    results['transcript_length'] = len(raw_transcript) if raw_transcript else 0
    
    # Wait for monitor to finish
    monitor_thread.join(timeout=1)
    if monitor_results:
        max_cpu = max(r['cpu_percent'] for r in monitor_results)
        max_memory = max(r['memory_mb'] for r in monitor_results)
        avg_cpu = sum(r['cpu_percent'] for r in monitor_results) / len(monitor_results)
        print(f"     Max CPU under transkribering: {max_cpu:.1f}%")
        print(f"     Medel CPU: {avg_cpu:.1f}%")
        print(f"     Max minne: {max_memory:.1f}MB")
    print()
    
    # STEP 5: Normalisering
    print("STEG 5: Normalisering (normalize_transcript_text)")
    print("-" * 70)
    from text_processing import normalize_transcript_text
    elapsed, normalized = benchmark_step(
        "Normalisera transkript",
        normalize_transcript_text,
        raw_transcript
    )
    results['normalize'] = elapsed
    print()
    
    # STEP 6: Processering
    print("STEG 6: Processering (process_transcript)")
    print("-" * 70)
    from text_processing import process_transcript
    elapsed, processed = benchmark_step(
        "Processera till struktur",
        process_transcript,
        normalized,
        "Test Projekt",
        "2026-01-02"
    )
    results['process'] = elapsed
    print()
    
    # STEP 7: Refinering
    print("STEG 7: Refinering (refine_editorial_text)")
    print("-" * 70)
    from text_processing import refine_editorial_text
    elapsed, refined = benchmark_step(
        "Refinera redaktionellt",
        refine_editorial_text,
        processed
    )
    results['refine'] = elapsed
    print()
    
    # STEP 8: Maskering
    print("STEG 8: Maskering (mask_text)")
    print("-" * 70)
    from text_processing import mask_text
    elapsed, masked = benchmark_step(
        "Maskera PII (normal)",
        mask_text,
        refined,
        "normal"
    )
    results['mask'] = elapsed
    print()
    
    # STEP 9: PII Gate Check
    print("STEG 9: PII Gate Check")
    print("-" * 70)
    from text_processing import pii_gate_check
    elapsed, (is_safe, reasons) = benchmark_step(
        "PII gate check",
        pii_gate_check,
        masked
    )
    results['pii_check'] = elapsed
    print()
    
    # SAMMANFATTNING
    print("=" * 70)
    print("SAMMANFATTNING - Flaskhalsar")
    print("=" * 70)
    print()
    
    total_time = sum(results.values())
    
    # Sort by time (descending)
    sorted_steps = sorted(results.items(), key=lambda x: x[1], reverse=True)
    
    print("Tid per steg (längst först):")
    print("-" * 70)
    for step_name, step_time in sorted_steps:
        if step_name == 'transcript_length':
            continue
        percentage = (step_time / total_time) * 100
        bar = "█" * int(percentage / 2)
        print(f"{step_name:25s} {step_time:7.2f}s ({percentage:5.1f}%) {bar}")
    
    print()
    print(f"Total tid: {total_time:.2f}s")
    print()
    
    # Identifiera flaskhalsar
    print("FLASKHALSAR (>10% av total tid):")
    print("-" * 70)
    bottlenecks = [s for s in sorted_steps if s[1] / total_time > 0.10 and s[0] != 'transcript_length']
    if bottlenecks:
        for step_name, step_time in bottlenecks:
            percentage = (step_time / total_time) * 100
            print(f"  ⚠️  {step_name}: {step_time:.2f}s ({percentage:.1f}%)")
    else:
        print("  ✅ Inga tydliga flaskhalsar (>10%)")
    print()
    
    # Rekommendationer
    print("REKOMMENDATIONER:")
    print("-" * 70)
    if results.get('transcribe', 0) > 60:
        print("  ⚠️  Transkribering tar >60s - överväg mindre modell (base/small)")
    if results.get('load_model', 0) > 10:
        print("  ⚠️  Modellladdning tar >10s - modellen är stor, men caches")
    if results.get('transcribe', 0) / total_time > 0.8:
        print("  ⚠️  Transkribering är >80% av total tid - detta är förväntat")
    
    max_step = max([s for s in sorted_steps if s[0] != 'transcript_length'], key=lambda x: x[1])
    print(f"  📊 Längsta steg: {max_step[0]} ({max_step[1]:.2f}s)")
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

