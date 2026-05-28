import os, json, sys, re

def contains_positive(text):
    pos = ['good','great','awesome','nice','cheap','affordable','love','excellent','happy','perfect','best']
    return any(w in text.lower() for w in pos)

def contains_negative(text):
    neg = ['bad','expensive','overpriced','terrible','hate','worst','poor','slow','issue','problem']
    return any(w in text.lower() for w in neg)

def set_relevance(comment):
    txt = comment.get('text','').lower()
    # include if personal experience, recommendation, value, opinion, comparison, critique
    if any(p in txt for p in ['i ', 'my ', 'we ', 'me ', 'our ', 'recommend', 'value', 'price', 'opinion', 'compare', 'critique', 'vs', 'vs.']):
        comment['relevance']='include'
        comment['relevanceReasoning']='Contains personal experience or opinion'
    else:
        comment['relevance']='exclude'
        comment['relevanceReasoning']='No personal experience or opinion detected'

def set_sentiment(comment):
    txt = comment.get('text','')
    if contains_positive(txt):
        comment['sentiment']='positive'
        comment['sentimentReasoning']='Positive language detected'
    elif contains_negative(txt):
        comment['sentiment']='negative'
        comment['sentimentReasoning']='Negative language detected'
    else:
        comment['sentiment']='neutral'
        comment['sentimentReasoning']='No strong sentiment words'

def classify(comment):
    if comment.get('classifyThis') and comment.get('relevance') is None:
        set_relevance(comment)
        set_sentiment(comment)
    for reply in comment.get('replies',[]):
        classify(reply)

def process_file(path):
    with open(path,'r',encoding='utf-8') as f:
        data=json.load(f)
    for c in data.get('comments',[]):
        classify(c)
    with open(path,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def main():
    if len(sys.argv)<2:
        print('Provide product slug')
        sys.exit(1)
    slug=sys.argv[1]
    base=os.path.join('batches',slug)
    if not os.path.isdir(base):
        print('No batches for',slug)
        return
    for f in os.listdir(base):
        if f.endswith('.json'):
            process_file(os.path.join(base,f))
    print('Done')

if __name__=='__main__':
    main()
