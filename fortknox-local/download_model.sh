#!/bin/bash
# Download script för LLM modeller - Välj modell

set -e

echo "=========================================="
echo "Fort Knox Local - Modell Nedladdning"
echo "=========================================="
echo ""
echo "Välj modell att ladda ner:"
echo ""
echo "1. Mistral 7B Instruct v0.3 (Rekommenderat för v1)"
echo "   - Stabil och beprövad"
echo "   - ~4GB"
echo ""
echo "2. Ministral-3-8B-Instruct-2512-GGUF (Upgrade path)"
echo "   - Bättre prestanda"
echo "   - Vision capabilities"
echo "   - ~4.5-5GB"
echo ""
read -p "Val (1-2, default 1): " choice
choice=${choice:-1}

case $choice in
    1)
        echo ""
        echo "Laddar ner Mistral 7B Instruct v0.3..."
        cd ~/.cache/fortknox/models
        if [ -f "download_mistral.sh" ]; then
            ./download_mistral.sh
        else
            echo "❌ download_mistral.sh inte hittad"
            echo "Kör manuellt:"
            echo "  huggingface-cli download bartowski/Mistral-7B-Instruct-v0.3-GGUF \\"
            echo "    mistral-7b-instruct-v0.3.Q4_K_M.gguf \\"
            echo "    --local-dir ~/.cache/fortknox/models \\"
            echo "    --local-dir-use-symlinks False"
        fi
        ;;
    2)
        echo ""
        echo "Laddar ner Ministral-3-8B-Instruct-2512-GGUF..."
        cd ~/.cache/fortknox/models
        if [ -f "download_ministral_3_8b_gguf.sh" ]; then
            ./download_ministral_3_8b_gguf.sh
        else
            echo "❌ download_ministral_3_8b_gguf.sh inte hittad"
            echo "Kör manuellt:"
            echo "  huggingface-cli download mistralai/Ministral-3-8B-Instruct-2512-GGUF \\"
            echo "    --include '*.gguf' \\"
            echo "    --local-dir ~/.cache/fortknox/models \\"
            echo "    --local-dir-use-symlinks False"
        fi
        ;;
    *)
        echo "Ogiltigt val"
        exit 1
        ;;
esac
