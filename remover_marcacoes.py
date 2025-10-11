#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import fitz  # PyMuPDF
from pathlib import Path

def is_reddish(rgb, thr_r=0.8, thr_gb=0.2):
    """Retorna True se a cor for considerada vermelho forte."""
    if not rgb or len(rgb) != 3:
        return False
    r, g, b = rgb
    return (r or 0) >= thr_r and (g or 0) <= thr_gb and (b or 0) <= thr_gb

def is_perfect_shape(drawing):
    """
    Retorna True se o desenho for um retângulo, quadrado ou círculo/elipse perfeita.
    """
    items = drawing.get("items", [])
    if not items:
        return False

    # Caso 1: Apenas um comando "re" (rectangle)
    if len(items) == 1 and items[0][0] == "re":
        return True

    # Caso 2: Detectar círculos/elipses perfeitas
    # Normalmente são compostos por curvas simétricas e fechadas
    if all(it[0] in ("c", "v", "y", "l") for it in items) and drawing.get("closePath", False):
        rect = drawing.get("rect")
        if rect:
            w = rect.width
            h = rect.height
            # Raio igual ou quase igual (diferença menor que 2 pontos)
            if abs(w - h) < 2:
                return True

    return False

def remove_reddish_vectors(page, r_thr=0.8, gb_thr=0.2, shrink=1.0, fill_white=False):
    """
    Remove vetores vermelhos irregulares sem tocar em imagens.
    """
    drawings = page.get_drawings()
    count = 0

    # Lista de áreas ocupadas por imagens
    image_rects = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            rects = page.get_image_bbox(xref)
        except Exception:
            continue
        if rects:
            if isinstance(rects, fitz.Rect):
                image_rects.append(rects)
            else:
                image_rects.extend(rects)

    for d in drawings:
        rect = d.get("rect")
        if rect is None:
            continue

        # Pular formas perfeitas (layout)
        if is_perfect_shape(d):
            continue

        stroke = d.get("color")
        fill = d.get("fill")

        if is_reddish(stroke, r_thr, gb_thr) or is_reddish(fill, r_thr, gb_thr):
            # Pular se tocar em imagem
            if any(rect.intersects(img_rect) for img_rect in image_rects):
                continue

            small_rect = rect + (-shrink, -shrink, shrink, shrink)
            page.add_redact_annot(
                small_rect,
                fill=(1, 1, 1) if fill_white else None,
                cross_out=False
            )
            count += 1

    if count:
        page.apply_redactions(images=0, graphics=2, text=1)
    return count

def process_pdf(input_path, output_path, r_thr=0.8, gb_thr=0.2, shrink=1.0, fill_white=False):
    with fitz.open(input_path) as doc:
        for page in doc:
            remove_reddish_vectors(page, r_thr=r_thr, gb_thr=gb_thr, shrink=shrink, fill_white=fill_white)
        doc.save(output_path, deflate=True, garbage=3)

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Remove vetores vermelhos irregulares, preservando formas do layout.")
    ap.add_argument("entrada", nargs="?", help="PDF de entrada")
    ap.add_argument("-o", "--saida", help="PDF de saída (padrão: *_sem_vetores.pdf)")
    ap.add_argument("--r-thr", type=float, default=0.8, help="Threshold mínimo de R (0..1)")
    ap.add_argument("--gb-thr", type=float, default=0.2, help="Threshold máximo de G/B (0..1)")
    ap.add_argument("--shrink", type=float, default=1.0, help="Encolher a área de remoção (pontos)")
    ap.add_argument("--fill-white", action="store_true", help="Pintar a área removida de branco")
    args = ap.parse_args()

    if not args.entrada:
        args.entrada = input("Digite o nome do PDF (sem extensão): ").strip()

    inp = Path(args.entrada)
    out = Path(args.saida) if args.saida else inp.with_name(inp.stem + "_sem_vetores.pdf")

    process_pdf(str(inp), str(out), r_thr=args.r_thr, gb_thr=args.gb_thr, shrink=args.shrink, fill_white=args.fill_white)
    print(f"Arquivo gerado: {out}")
