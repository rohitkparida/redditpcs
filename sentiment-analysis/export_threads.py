import glob
import json
from pathlib import Path

def main():
    files = glob.glob('public/sentiment-evidence/**/threads.json', recursive=True)
    out_lines = []
    
    for idx, f in enumerate(sorted(files)):
        try:
            with open(f, 'r', encoding='utf-8') as file_obj:
                data = json.load(file_obj)
            
            prod_name = data.get("productName", "Unknown")
            # Extract category name from path directory (parent of threads.json)
            category = Path(f).parent.name
            
            out_lines.append(f"=== PRODUCT: {prod_name} (Dir: {category}) ===")
            
            threads = data.get("threads", [])
            for t_idx, t in enumerate(threads):
                url = t.get("url", "No URL")
                # Top comment text is usually the thread title if depth is 0
                title = "No Title"
                if t.get("topComments"):
                    title = t["topComments"][0].get("text", "No Title").replace('\n', ' ')
                    if len(title) > 120:
                        title = title[:120] + "..."
                
                out_lines.append(f"  [{t_idx+1}] TITLE: {title}")
                out_lines.append(f"      URL: {url}")
            out_lines.append("") # empty line separator
            
        except Exception as e:
            out_lines.append(f"=== ERROR READING {f}: {e} ===\n")
            
    with open('sentiment-analysis/all_threads_to_verify.txt', 'w', encoding='utf-8') as out_f:
        out_f.write('\n'.join(out_lines))
    print(f"Exported threads summary to sentiment-analysis/all_threads_to_verify.txt")

if __name__ == '__main__':
    main()
