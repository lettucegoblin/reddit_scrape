import praw
import json
import time
import os
import pprint
import math

def load_config():
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config

rate_limit_timeout = 15 * 60 # 15 minutes

config = load_config()
# Replace these with your credentials
reddit = praw.Reddit(
    client_id=config['client_id'],
    client_secret=config['client_secret'],
    user_agent=config['user_agent'],
    ratelimit_seconds=300
)
save_dir = config['save_dir']
os.makedirs(save_dir, exist_ok=True)

def get_rate_limit():
    current_rate_limit = reddit.auth.limits
    print(f"Rate limit: {current_rate_limit['remaining']} requests remaining in {current_rate_limit['reset_timestamp'] - time.time()} seconds")
    return current_rate_limit
# handle rate limit
def handle_rate_limit():
    time.sleep(10) # wait 10 seconds
    current_rate_limit = get_rate_limit()
    rate_limit_timeout = abs(current_rate_limit['reset_timestamp'] - time.time()) + 30
    print(f"Rate limit reached. Waiting for {rate_limit_timeout / 60} minutes...")
    
    time.sleep(rate_limit_timeout)
    print("Resuming...")
    current_rate_limit = get_rate_limit()
    


def get_top_subreddits():
    # scrape top subreddits, or load from file if it exists
    try:
        with open(f'{save_dir}/top_subreddits.json', 'r') as file:
            top_subreddits = json.load(file)
    except FileNotFoundError:
        top_subreddits = scrape_top_subreddits()
        # cache top_subreddits to file
        with open(f'{save_dir}/top_subreddits.json', 'w') as file:
            json.dump(top_subreddits, file, indent=4)

    # make a set of subreddit names to ensure no duplicates
    subreddit_names = set()
    for subreddit_id in top_subreddits:
        subreddit_names.add(top_subreddits[subreddit_id]['subreddit'])
    
    return list(subreddit_names)

def scrape_top_subreddits():
    top_subreddits = {}
    for submission in reddit.subreddit('all').top(limit=800):
        print(submission.title, submission.subreddit.display_name)
        top_subreddits[submission.id] = {
            'id': submission.id,
            'title': submission.title,
            'score': submission.score,
            'url': submission.url,
            'subreddit': submission.subreddit.display_name,
            'subreddit_id': submission.subreddit.id,
            'subreddit_subscribers': submission.subreddit.subscribers,
            'subreddit_active_users': submission.subreddit.active_user_count,
            'subreddit_accounts_active': submission.subreddit.accounts_active,
            'subreddit_over18': submission.subreddit.over18,
            'subreddit_description': submission.subreddit.description,
            'subreddit_public_description': submission.subreddit.public_description,
            'subreddit_created_utc': submission.subreddit.created_utc,
            
        }
        time.sleep(3)
    return top_subreddits

def get_top_comments(subreddit_name, submission):
    # scrape top comments, or load from file if it exists
    try:
        os.makedirs(f'{save_dir}/{subreddit_name}', exist_ok=True)
        with open(f'{save_dir}/{subreddit_name}/{submission.id}_top_comments.json', 'r') as file:
            top_comments = json.load(file)
    except FileNotFoundError:
        top_comments = scrape_top_comments(submission)
        # cache top_comments to file
        with open(f'{save_dir}/{subreddit_name}/{submission.id}_top_comments.json', 'w') as file:
            json.dump(top_comments, file, indent=4)

def get_author_info(author):
    if(not author):
        return {
            'author_name': '[deleted]',
            'is_suspended': True
        }
    author_data = {
        'author_name': author.name,
        'is_suspended': author.is_suspended if hasattr(author, 'is_suspended') else False
    }

    #Suspended/banned accounts will only return the name and is_suspended attributes.
    if(not author_data['is_suspended']):
        author_data['author_fullname'] = author.fullname
        author_data['author_id'] = author.id
        author_data['author_created_utc'] = author.created_utc
        author_data['is_mod'] = author.is_mod
        author_data['is_gold'] = author.is_gold
        author_data['is_employee'] = author.is_employee
        author_data['icon_img'] = author.icon_img
        author_data['link_karma'] = author.link_karma #The user's link karma. Which is the sum of all karma gained from links the user has submitted.
        author_data['awarder_karma'] = author.awarder_karma #The user's awarder karma. Which is the sum of all karma gained from giving awards.
        author_data['comment_karma'] = author.comment_karma #The user's comment karma. Which is the sum of all karma gained from comments the user has submitted.
        author_data['total_karma'] = author.total_karma #The user's total karma. Which is the sum of all karma the user has gained.

    return author_data

def scrape_top_comments(submission):
    top_comments = {}
    submission.comments.replace_more(limit=1)
    # top 10 top level comments
    comment_list = submission.comments.list()
    i = 0
    while i < len(comment_list):
        comment = comment_list[i]
        try:
            comment_data = {
                'id': comment.id,
                'parent_id': comment.parent_id,
                'link_id': comment.link_id,
                'is_submitter': comment.is_submitter,
                'permalink': comment.permalink,
                'created_utc': comment.created_utc,
                'body': comment.body,
                'body_html': comment.body_html,
                'distinguished': comment.distinguished,
                'subreddit_id': comment.subreddit_id,
                'score': comment.score,
                'stickied': comment.stickied,
            }
            comment_data['author'] = get_author_info(comment.author)
            top_comments[comment_data['id']] = comment_data
            print(f"Scraped comment {i + 1} of {len(comment_list)}")
            # print if comment is a reply and what the text is
            i += 1
            # sleep for 1 second to respect rate limit
            time.sleep(0.1)
        except Exception as e:
            print(f"Error occurred: {e}")
            if(e.response.status_code == 404 and '.com/user/' in e.response.url):
                # user has been deleted
                i += 1
                print(f"User https://www.reddit.com/user/{comment.author.name} has been deleted.")
            else:
                handle_rate_limit()
    get_rate_limit()
    return top_comments

def save_top_posts_json(subreddit_name, top_posts):
    with open(f'{save_dir}/{subreddit_name}_top_posts.json', 'w') as file:
        json.dump(top_posts, file, indent=4)

def get_top_posts(subreddit_name, limit=100):
    # scrape top posts, or load from file if it exists
    try:
        with open(f'{save_dir}/{subreddit_name}_top_posts.json', 'r') as file:
            top_posts_json = json.load(file)
            top_posts = top_posts_json
    except FileNotFoundError:
        top_posts_json = None
        top_posts = scrape_top_posts(subreddit_name, limit)
        # cache top_posts to file
        save_top_posts_json(subreddit_name, top_posts)

    if(top_posts_json is not None):
        if(len(top_posts_json) < limit):
            top_posts = scrape_top_posts(subreddit_name, limit, top_posts_json)
            top_posts.update(top_posts_json)
            save_top_posts_json(subreddit_name, top_posts)
    return top_posts

def scrape_top_posts(subreddit_name, limit=100, json_file=None):
    top_posts = {} # dict of id: post_data
    post_list =  reddit.subreddit(subreddit_name).top(limit=limit)
    count = 0
    for submission in post_list:
        while True:
            try:
                # if post is in json_file, skip it
                if(json_file is not None and submission.id in json_file):
                    print(f"Skipping {submission.title}")
                    break
                print(submission.title)
                #pprint.pprint(vars(submission))
                post_data = {
                    'author_fullname': submission.author_fullname if submission.author else '[deleted]',
                    'author_name': submission.author.name if submission.author else '[deleted]',
                    'created_utc': submission.created_utc,
                    'domain': submission.domain,
                    'gilded': submission.gilded,
                    'gildings': submission.gildings,
                    'id': submission.id,
                    'is_created_from_ads_ui': submission.is_created_from_ads_ui,
                    'is_original_content': submission.is_original_content,
                    'is_reddit_media_domain': submission.is_reddit_media_domain,
                    'is_self': submission.is_self, # is a text post
                    'is_video': submission.is_video,
                    'link_flair_text': submission.link_flair_text if submission.link_flair_text else '',
                    'media_only': submission.media_only,
                    'num_comments': submission.num_comments,
                    'over_18': submission.over_18,
                    'permalink': submission.permalink,
                    'score': submission.score,
                    'subreddit': subreddit_name,
                    'subreddit_id': submission.subreddit.id,
                    'text': submission.selftext if submission.is_self else None,
                    'title': submission.title,
                    'total_awards_received': submission.total_awards_received,
                    'upvote_ratio': submission.upvote_ratio,
                    'url': submission.url
                }
                top_posts[submission.id] = post_data
                # sleep for 1 second to respect rate limit
                time.sleep(0.2)
                #save to file every 50 posts
                if(count % 50 == 0):
                    save_top_posts_json(subreddit_name, top_posts)
                break # break out of while loop
            except Exception as e:
                print(f"Error occurred: {e}")
                handle_rate_limit()
    return top_posts

def number_of_posts_we_have(subreddit_name):
    # checks the data/subreddit_name_top_posts.json file to see how many posts we have
    try:
        with open(f'{save_dir}/{subreddit_name}_top_posts.json', 'r') as file:
            top_posts_json = json.load(file)
            top_posts = top_posts_json
            print(f"Found {len(top_posts)} posts in {subreddit_name}_top_posts.json")
            #return len(top_posts)
            # check if we have all the posts by checking if each post has a folder
            count = 0
            for post_id in top_posts:
                if(os.path.exists(f'{save_dir}/{subreddit_name}/{post_id}_top_comments.json')):
                    count += 1
            print(f"Found {count} posts in {subreddit_name} folder")
            return count
        
    except FileNotFoundError:
        return 0
    return 0

def scrape_reddit_data(post_limit=100, comment_limit=100):
    """
    Scrape top posts & top comments from top 100 subreddits; respecting rate limits.
    Allows for pause/resume functionality by saving json data checkpoints.
    """

    top_subreddits = get_top_subreddits()

    #top_subreddits = ['AmItheAsshole']


    data = {}
    for subreddit_name in top_subreddits:
        print(f"Scraping top posts from {subreddit_name}...")
        if(number_of_posts_we_have(subreddit_name) >= post_limit):
            print(f"Already have {post_limit} posts from {subreddit_name}. Skipping...")
            continue
        while True:
            try:
                top_posts = get_top_posts(subreddit_name, post_limit)
                
                # scrape top comments for each post
                for post_id in top_posts:
                    submission = reddit.submission(id=post_id)
                    top_posts[post_id]['top_comments'] = get_top_comments(subreddit_name, submission)
                data[subreddit_name] = top_posts
                print(f"Scraped {len(top_posts)} posts from {subreddit_name}.")
                print(f"Total posts scraped: {len(data)}")
                print(f"Waiting for {rate_limit_timeout / 60} minutes...")
                time.sleep(rate_limit_timeout) # wait 1 minute between subreddits

                break
            except praw.exceptions.RedditAPIException as e:
                if "you are doing that too much" in str(e).lower():
                    handle_rate_limit()
                else:
                    print(f"An error occurred while scraping {subreddit_name}: {str(e)}")
                    # save error to file append to error file
                    with open(f'{save_dir}/errors.txt', 'a') as file:
                        file.write(f"An error occurred while scraping {subreddit_name}: {str(e)}\n")
                    #sleep for 5 minutes
                    time.sleep(5 * 60)
                    handle_rate_limit()
                    #break
    return data



def save_to_json(data):
    with open('reddit_data.json', 'w') as file:
        json.dump(data, file, indent=4)

if __name__ == '__main__':
    reddit_data = scrape_reddit_data(10, 10)
    save_to_json(reddit_data)
    print("Data has been saved to reddit_data.json")