import os
import re
import codecs

from data_utils import create_dico, create_mapping, zero_digits
from data_utils import iob2, iob_iobes, get_seg_features


def load_sentences(path, lower, zeros):
    """
    Load sentences. A line must contain at least a word and its tag.
    Sentences are separated by empty lines.
    """
    sentences = []
    sentence = []
    num = 0
    for line in open(path, 'r',encoding='utf8'):
        num+=1
        line = zero_digits(line.rstrip()) if zeros else line.rstrip()
        # print(list(line))
        if not line:#�Կ�����Ϊһ�仰�����ı�־
            if len(sentence) > 0:
                sentences.append(sentence)
            sentence = []
        else:
            if line[0] == " ": #���ܻ���д������������һ������д���˿ո񣬳��ڿ��Բ�����
                line = "$" + line[1:]
                word = line.split()
                # word[0] = " "
            else:
                word= line.split( )
            assert len(word) == 2  #����ȷ��һ��ȷʵ������
            sentence.append(word)
    if len(sentence) > 0:
        #if 'DOCSTART' not in sentence[0][0]:
        sentences.append(sentence)
    return  sentences


def update_tag_scheme(sentences, tag_scheme):
    """
    Check and update sentences tagging scheme to IOB2.
    Only IOB1 and IOB2 schemes are accepted.
    """
    for i, s in enumerate(sentences):
        tags = [w[-1] for w in s]
        # Check that tags are given in the IOB format
        if not iob2(tags):
            s_str = '\n'.join(' '.join(w) for w in s)
            raise Exception('Sentences should be given in IOB format! ' +
                            'Please check sentence %i:\n%s' % (i, s_str))
        if tag_scheme == 'iob':
            # If format was IOB1, we convert to IOB2
            for word, new_tag in zip(s, tags):
                word[-1] = new_tag
        elif tag_scheme == 'iobes':
            new_tags = iob_iobes(tags)
            for word, new_tag in zip(s, new_tags):
                word[-1] = new_tag
        else:
            raise Exception('Unknown tagging scheme!')


def char_mapping(sentences, lower):
    """
    Create a dictionary and a mapping of words, sorted by frequency.
    """
    chars = [[x[0].lower() if lower else x[0] for x in s] for s in sentences] #ÿ����תСд
    dico = create_dico(chars) #ͳ�ƴ�Ƶ�����ɴ�Ƶ�ֵ�
    dico["<PAD>"] = 10000001  #����padding����һ���ܴ������Ϊ�˺���padding��
    dico['<UNK>'] = 10000000  #����δ֪���ַ���Ҳ��һ���ܴ����
    char_to_id, id_to_char = create_mapping(dico)
    #print("Found %i unique words (%i in total)" % (
    #    len(dico), sum(len(x) for x in chars)
    #))
    return dico, char_to_id, id_to_char


def tag_mapping(sentences):
    """
    Create a dictionary and a mapping of tags, sorted by frequency.
    """
    
    f=open('tag_to_id.txt','w',encoding='utf8')
    f1=open('id_to_tag.txt','w',encoding='utf8')
    tags=[]
    
    for s in sentences:
    #s������[['ȥ',O],['��',B-Tes]]����
        ts=[]
        for char in s:
            tag=char[-1] #ȡ����ǩ
            ts.append(tag)
        tags.append(ts)
    #������ο���д��һ�仰
    #tags = [[char[-1] for char in s] for s in sentences]
    
    #tags1 = [[char[-1] for char in s] for s in sentences]
    dico = create_dico(tags)  #ͳ�ƴ�Ƶ��������Ƶ�ֵ�
    tag_to_id, id_to_tag = create_mapping(dico)
    #print("Found %i unique named entity tags" % len(dico))
    #����ֻ��Ϊ��д���ļ��￴��
    for k,v in tag_to_id.items():
        f.write(k+":"+str(v)+"\n")
    for k,v in id_to_tag.items():
        f1.write(str(k) + ":" + str(v) + "\n")
    return dico, tag_to_id, id_to_tag


def prepare_dataset(sentences, char_to_id, tag_to_id, lower=False, train=True):
    
    """
    Prepare the dataset. Return a list of lists of dictionaries containing:
        - word indexes
        - word char indexes
        - tag indexes
    """

    none_index = tag_to_id["O"]

    def f(x):
        return x.lower() if lower else x
    data = []
    for s in sentences:
        #print(sentences)
        string = [w[0] for w in s]
        chars = [char_to_id[f(w) if f(w) in char_to_id else '<UNK>']
                 for w in string] #��ÿ���ֽ����ж��Ƿ��ڴ�Ƶ�ֵ������У������֣�û�У������Լ���ӵ�<UNK>
        #����ÿ���ֶ�����ID�������ҵ�ÿ���ֶ�Ӧ��ID��������Щ�����ֵ�������֣����ص����ֵ���<UNK>��ID
        #�����Ҫ�������Щ����ѵ���ֵ�����ֵ��������Ϊ�µ�ѵ�������кܿ��ܰ����µ��֣�������ѵ���ֵ������Щδ��¼�Ĵ�
        segs = get_seg_features("".join(string))  #��ȡÿ���ֵ��д���Ϣ
        if train:
            tags = [tag_to_id[w[-1]] for w in s]
        else:
            tags = [none_index for _ in chars]
        data.append([string, chars, segs, tags]) #[һ�仰��ÿ����,�ֶ�Ӧ��ID,�ֶ�Ӧ���д���Ϣ,��ǩID]

    return data


def augment_with_pretrained(dictionary, ext_emb_path, chars):
    #dictionaryΪѵ�����Ĵ�Ƶ�ֵ䣬ext_emb_pathΪ�������ļ���charsΪ���Լ���������ɵ��б�
    #��Ҫ��Ϊ��ȷ���������ļ��������ֶ��ڴ�Ƶ�ֵ����У����ޣ�����ӣ�����0
    """
    Augment the dictionary with words that have a pretrained embedding.
    If `words` is None, we add every word that has a pretrained embedding
    to the dictionary, otherwise, we only add the words that are given by
    `words` (typically the words in the development and test sets.)
    """
    #print('Loading pretrained embeddings from %s...' % ext_emb_path)
    assert os.path.isfile(ext_emb_path)

    # Load pretrained embeddings from file
    #ext_emb_path���������ļ�����һ���ּ�һ���ո񣬺����������ֵ�������ʾ
    #���漴�����ļ��зǿ��еĵ�һ�����Ӷ��ó������ŵ�һ��set��
    #�ʶ�pretrained���Ǵ��������ļ���ȡ�������е���
    pretrained = set([
        line.rstrip().split()[0].strip() #������ÿ�����Ļ��з�
        for line in codecs.open(ext_emb_path, 'r', 'utf-8')
        #if len(ext_emb_path) > 0
    ])

    # We either add every word in the pretrained file,
    # or only words given in the `words` list to which
    # we can assign a pretrained embedding
    #���û�в��Լ������ֻ���������������������������ڴ�Ƶ�ֵ��еģ����ӵ���Ƶ�ֵ������ơ�
    #����в��Լ��������һ����Լ����Ѳ��Լ�����Щ������������������������ѵ������Ƶ�ֵ�ģ��ӵ��ֵ������ơ�
    #�ʶ��������ȣ�ѵ�����д��ڵ��ֿ϶�����Ҫ����Σ���ֻ�����������д��ڵ���Щ�֣����ǲ�һ����Ҫ������������ȫ��һ�飬������Լ���������ֵĻ����ͼӵ�ѵ��������û�У��Ͳ���Ҫ�ˡ�
    #�����˴�Ƶ�ֵ�֮������ȷ��ID��ϵ
    if chars is None:
        for char in pretrained:
            if char not in dictionary:
                dictionary[char] = 0  #��������������ļ�������ڴ�Ƶ�ֵ��������ϲ���ֵ0
    else:
        for char in chars:
            if any(x in pretrained for x in [
                char,
                char.lower(),
                re.sub('\d', '0', char.lower())
            ]) and char not in dictionary: #�����ǰ���֡���Сд���������ָ�д������̬����ĳ����̬�������������У������ֲ������ڴ�Ƶ�ֵ����
                dictionary[char] = 0  #������ϣ�����ֵ0
            #����˵��������Լ��е��������������ļ��ﲻ���ڵģ��Ͳ���ӵ���Ƶ�ֵ����ˡ�

    word_to_id, id_to_word = create_mapping(dictionary)
    #���ʱ���id��Ӧ�ǱȽ�������
    return dictionary, word_to_id, id_to_word


def save_maps(save_path, *params):
    """
    Save mappings and invert mappings
    """
    pass
    # with codecs.open(save_path, "w", encoding="utf8") as f:
    #     pickle.dump(params, f)


def load_maps(save_path):
    """
    Load mappings from the file
    """
    pass
    # with codecs.open(save_path, "r", encoding="utf8") as f:
    #     pickle.load(save_path, f)

