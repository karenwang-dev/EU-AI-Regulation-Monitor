You only need the frontier model for one single edit | Hacker News
Hacker News
new
|
past
|
comments
|
ask
|
show
|
jobs
|
submit
login




You only need the frontier model for one single edit
(
stencil.so
)
156 points
by
jxmorris12
14 hours ago
|
hide
|
past
|
favorite
|
48 comments




help












ghiculescu
51 minutes ago
|
next
[–]








> We upstreamed it to omp


For those not sufficiently cracked... what is omp? Is there a way I can have this command or workflow in Cursor / Claude Code?


I tried going to the homepage (
https://stencil.so/
). It didn't really help.






reply










rootlocus
48 minutes ago
|
parent
|
next
[–]








https://omp.sh/
- It's maintained by the author of the article.






reply










nxtfari
4 hours ago
|
prev
|
next
[–]








This is really smart, like the author said, old idea but cleverly applied.


In case anyone wants a summary: don’t one shot, don’t use plan mode and hand off the plan to cheap executors, ask the frontier model to explore, create a todo list, and then start when it feels confident; stop it after first code edit, then prefill the context to cheap executor to continue.






reply










heisenbit
20 minutes ago
|
prev
|
next
[–]








I‘m really wondering about plan and then agent mode switch in Copilot even with the same model. The switch swaps the prompt so all the learnings during planning which are in the cache will get invalidated.






reply










Too
4 hours ago
|
prev
|
next
[–]








>
The mistake is upstream of the architecture diagram. People price agents the way they price people: senior time is expensive, so minimize senior involvement.


>
But the expensive part of an agent's day is not the fixing, building, or even the thinking. Opus fixing things does not cost money. Opus reading things costs money.


Heh, another rediscovery that agents and humans are alike. By the time I've researched a Jira ticket and made it unambiguous enough to outsource, I might as well have written the code myself instead.






reply










wordpad
4 hours ago
|
parent
|
next
[–]








You are more proficient at writing code than ai specs.


You could get better/faster at writing good specs and its a higher cap skill now.


For low risk changes you could let llm write its own spec from high level requirements and just validate its assumptions/design decisions.






reply










figmert
10 hours ago
|
prev
|
next
[–]








The reason I use plan then implement is because I can adjust the plan, whereas if I get it to implement straight away, it might (and often does) make the wrong decisions that will be harder to adjust, or I'd have to adjust it after the fact.






reply










canpan
9 hours ago
|
parent
|
next
[–]








One big pain point is not seeing the thinking trace. I noticed using pi with a self hosted model that I could spot, stop and correct my prompt much faster. With claude etc I have to first wait for it to think 3 minutes and then notice it got completely off the path I wanted.


I still use a plan, because my local model is not as smart as opus, but I can iterate much faster.






reply










WilcoKruijer
2 hours ago
|
root
|
parent
|
next
[–]








I’ve seen people have success figuring out model reasoning by adding a required `reasoning` parameter to tool calls. Might be worth experimenting with this for the `write` tool call in a coding agent harness.






reply










embedding-shape
2 hours ago
|
root
|
parent
|
next
[–]








Also "divide and conquer" is still applicable. Tired of waiting 10 minutes for the model to come up with a plan that ends up being wrong? Divide the problem into pieces and attack the pieces individually, worst case scenario the model spends 2 minutes and got some detail wrong, but way easier to correct the tiny stuff.


Once you've done with the pieces, do one "integrate them together" part, then you have a fully formed plan with less chance of wrong stuff in it. Yes, this requires a bit more interactivity than "prompt model then come back after making and drinking a coffee", but personally I prefer that.






reply










carterschonwald
8 hours ago
|
root
|
parent
|
prev
|
next
[–]








this so true.  its really hard to make sure a model isnt going off the rails if i dont see full cot.  the fact that oai and anthropic models hide it now has made them less reliable. which is a shame






reply










trollbridge
7 hours ago
|
root
|
parent
|
next
[–]








The great news is you can use DS-V-Pro, MiMo-V2.5-Pro, GLM-5.2, or K3 and see everything.


I tend to use 5.6-Sol now more for one shot type of tasks where all I want is the answer and I’m not going to read the reasoning.






reply










andreyvit
3 hours ago
|
prev
|
next
[–]








It's hard to argue with the numbers, but starting with a (mostly true!) “research is the most expensive part” premise, this strikes me as an odd direction to go to optimize costs:


1. As others pointed out, we feed all the same research turns to a smaller model, so we pay the uncached price for all of them.


2. During research, the model typically reads more code than is relevant, to figure out what is relevant and what is not. If that's the expensive part, we keep paying for those turns with the most expensive model?


3. There is no quality comparison of the resulting code. Same plan != same code, and AI tokens during the initial implementation phase isn't the only cost attributable to the task.


I do the opposite:


1. Outsource research to a subagent, or several parallel subagents. Let them output the relevant code paths only. Using gpt-5.6-terra-high on Codex and sonnet on Claude. Merge results into a single per-task research file. This saves tokens and context window of the bigger model, and avoids re-researching after compactions and in subagents.


2. Use the smartest agent (Sol xhigh ultra / Fable max) for both planning and execution. Tell it to use the research file where possible.


3. Switch to dumber agents for verbose substeps, e.g. gpt-5.6-luna-medium / sonnet is enough to drive browser use.


Sadly, got no numbers to back this approach.


PS: Of course, different task complexities and codebase complexities demand different approaches. The most expensive part is actually the code review step, which they don't mention/have at all. We should come up with some sort of complexity grading, so that discussions like this can be contextualized.






reply










pmontra
1 hour ago
|
parent
|
next
[–]








I've been doing more or less this (from the post) for months:


> plan deeply, then capture the plan as a todo list, then start.


I do the plan deeply phase by writing a 50 line specification myself and then asking Claude to evaluate it, find what I missed, ask questions. I answer the question and we iterate until I know that we have what I had in mind to do.


Then I ask it to write the implementation plan, that I might end up reviewing because it always asks some more question. Finally it implements the steps.


If the planning was good the implementation is fast.






reply










_ink_
3 hours ago
|
prev
|
next
[–]








> Below: the share of runs that went poking around the web for it. Filthy cheaters!


I can understand that in their benchmark setting they wouldn't want the model to find an existing solution. But in my day to day work, wouldn't I want the model to search online for the best solution? Am I not shooting myself in the foot by preventing it?






reply










leobg
1 hour ago
|
prev
|
next
[–]








I guess Anthropic knows this. They show you this warning:


---
Switch model?
Your next response will be slower and use more tokens


This conversation is cached for the current model. Switching to Opus 4.8 (1M context) means the full history gets re-read on your next message.
---


Reminds me a bit of airline booking sites ("We noticed you didn't add insurance").






reply










wrs
12 hours ago
|
prev
|
next
[–]








Lately I'm trying a variation on this: Have the main agent make a phased implementation plan, then for each phase, have it start an implementation subagent with a focused prompt, then review that agent's work in the main session. The theory being that the main session still contains all the research, but it can review just the diff rather than have the entire implementation session in context as well.


The post doesn't include a review in the cost comparison, but I find that immediately doing a review catches lots of mistakes.






reply










sgc
8 hours ago
|
parent
|
next
[–]








Actually it does include an important level of review. They say "init a TODO list with a validation step for each item", and then the last several sections of the execution are within the TODO - where it is validating the code.


To me that was the heart of the article and of what they did - create a self-validating todo list that deterministically forces the agents to stay on task, and then trim out just the right extraneous context (the actual planning) without messing with the read-file context which is where they found subagents burning most of their tokens.


Just a few days ago I was speculating about forking context to implement instead of spawning subagents here on hn. This is similar to that just several more steps more sophisticated. You could even fork the trimmed context here for very large tasks.






reply










bensyverson
7 hours ago
|
parent
|
prev
|
next
[–]








Yes, this is a core part of my workflow; use the smartest model (e.g. Fable) to generate a large hierarchical implementation plan, then clear the context and have a lesser model (e.g. Sonnet) track and execute the plan [0], often in parallel.


It all depends on how much work you're doing; if it's a simple task, there's virtually no need for plans at all; just have the smart agent do it. But if the work is going to take 5, 10 or 100 sessions, there's real value in the "smart agent plans, cheap agent executes" model.


[0]:
https://github.com/bensyverson/jobs






reply










ricardobeat
6 hours ago
|
root
|
parent
|
next
[–]








This is exactly what the post argues
against
though, as it leads to higher overall cost.






reply










pqdbr
10 hours ago
|
parent
|
prev
|
next
[–]








I’m using Claude code dynamic workflow like this. I tell Fable to use a workflow. He is the planner, orchestrator and reviewer. Opus agents are implementers. Works unbelievably well.






reply










oliver236
4 hours ago
|
root
|
parent
|
next
[–]








can you explain this in a bit more detail? super interested






reply










danielciocirlan
9 hours ago
|
root
|
parent
|
prev
|
next
[–]








“He”






reply










brabel
1 hour ago
|
root
|
parent
|
next
[–]








In many languages that’s the only way to express that since there is no “it”. It doesn’t mean speakers of such languages anthropofy everything and I think that’s the case here.






reply










llbbdd
8 hours ago
|
root
|
parent
|
prev
|
next
[–]








I call him "my son"






reply










Incipient
1 hour ago
|
prev
|
next
[–]








Wait this is new? Large context models figure out the architecture of the request. Miss sized models plan out each requirement, and smaller models implement a tightly detailed task? Isn't this the standard approach?






reply










benrutter
31 minutes ago
|
parent
|
next
[–]








> Miss sized models plan out each requirement, and smaller models implement a tightly detailed task? Isn't this the standard approach?


It is, but the article is suggesting something different. The central idea is to use /prewalk to load slightly edited context from the more expensive model into the one, so that the cheaper model doesn't burn tokens reading all the files again.






reply










hankbond
11 hours ago
|
prev
|
next
[–]








Does anyone have a name for that really neat "the bar chart is a bookshelf, you can hover a spine to see the cover" vis?  I've never seen it before.






reply










nchmy
10 hours ago
|
prev
|
next
[–]








This entire argument rests upon the fact that Gemini Flash ain't cheap.


Try plan with opus 4.8 and then implement with Deepseek v4 flash - its 35x cheaper for reads, 90x cheaper writes, and 18x cheaper cache reads.


Or plan with Deepseek Pro, or even Flash itself. I've been impressed with both.






reply










pdyc
4 hours ago
|
parent
|
next
[–]








+1. i have similar workflow and i use local models on igpu so token cost is free and electricity cost is in cents.






reply










spuz
1 hour ago
|
root
|
parent
|
next
[–]








I cannot imagine local models running on an igpu could get anything close to either a useful plan or execution of a plan. I've tested Qwen 3.5 27B locally and its solutions to coding problems are usually flawed and running in thinking mode is too slow and that's on a discrete GPU. How do you get anything useful done on a model that runs on an igpu?






reply










ricardobeat
6 hours ago
|
prev
|
next
[–]








I just did this five minutes ago. Started a task with Kimi K3, noticed cost going up, switched to Minimax M3 continuing from the same context. Really easy to do with Crush/OpenCode.


It works quite well most of the time. For very deeply technical tasks, where exploration involves multiple agents (and blowing up context limits a few times), I'll have a plan written down to disk that will be much longer than 2k tokens.






reply










pistoriusp
13 hours ago
|
prev
|
next
[–]








Apparently "/prewalk" is built into
https://github.com/can1357/oh-my-pi
, which I guess is a lot like "Oh My ZSH?" Pi with batteries included.


There are a lot of interesting ideas in it, mostly none that I have applied to my own workflows. Curious if anyone has used it?






reply










AshamedBadger56
13 hours ago
|
parent
|
next
[–]








I've played around with all the popular agent CLI's and I've landed on omp/ohmypi as my favorite for now. It's definitely the opposite of a lean install like Pi, but I find it works a lot better than OpenCode. It's also very very active, with a lot of cool new ideas like this prewalk in it.






reply










rwc
11 hours ago
|
prev
|
next
[–]








Just specify that the more efficient model should only be used if the cost of doing the task would be less than using the higher horsepower model. Fable has no problem routing based on that instruction.






reply










egamirorrim
4 hours ago
|
prev
|
next
[–]








Isn't part of this the inevitable cache invalidation that comes from switching between providers (Opus to Gemini)?






reply










Aeolun
3 hours ago
|
parent
|
next
[–]








Yeah, but you only pay the switch on the much cheaper model, the first bit is done with smaller context on the expensive model, so you still save money in the end.






reply










the_gipsy
13 hours ago
|
prev
|
next
[–]








> Senior architect, junior engineer. Sounds great, right?


Sounds like a consulting slaughterhouse. Picture Java Enterprise Solutions. As we all know, the pinnacle of software engineering.






reply










swiftcoder
4 hours ago
|
parent
|
next
[–]








Hah. Yeah. Weirdly, most software managers also seem to believe this whole "senior writes a plan, junior implements" is cost-effective (it typically isn't, one should invest in hiring/promoting more seniors).






reply










Almondsetat
12 hours ago
|
prev
|
next
[–]








Did they also use Gemini Flash to write this article? Because, frankly, it's unbearable






reply










IshKebab
3 hours ago
|
parent
|
next
[–]








Very clearly. Even if you have no qualms with AI I don't understand why people think writing in this cliched style is ok.


On the other hand people thought it was fine to use cliched titles like "The unreasonable effectiveness of..", "... for fun and profit", "The rise and fall of ...", "All you need is ...", etc. etc.


So I guess there's just a large portion of writers that are immune to cliche? Pretty annoying anyway.






reply










pphysch
10 hours ago
|
prev
|
next
[–]








> Any agent, any model, any scaffold: the bill is essentially O(reads)


Therefore token sellers have incentive to produce verbose, unreadable code






reply










pixl97
9 hours ago
|
parent
|
next
[–]








Whichever token seller defects can capture a larger chunk of the market with slimmer code.






reply










pphysch
6 hours ago
|
root
|
parent
|
next
[–]








Do you think the average vibe coder or AI-smitten suit cares about slim code? A lot of folks still think "LOC = good" in 2026. It will be a hard sell for the practical engineer.


Even if they understand "slim code = fewer tokens = less spend" they still have to grok that less code is not less functionality.






reply










viccis
11 hours ago
|
prev
|
next
[–]








From what I can tell, I have a similar workflow. I get Fable 5 / Sol on High to talk to me about requirements until it's ready to design. I then have it break the design into tickets. I use kata, an agent-oriented issue tracker. If it ever starts to get bloated, I'll just make my own as it doesn't need too many features. Anyway, I tell it to include sufficient context in each such ticket to be picked up by a new implementation agent. Explicit user stories, Cucumber style acceptance criteria, etc.


When it's done, I switch to a smaller model and tell it to start a /goal of calling `kata ready` to get tickets ready to be worked. Work one ticket on each goal iteration, committing changes when done. Stop when all the tickets are either closed out or are blocked on actions from me.


It works fantastically. I can get entire (relatively straightforward) iOS apps done in under my $20/month five hour session window.


I get even better results if I do the QA session with the frontier model with two output artifacts: an implementation spec and a design prompt for Claude Design. I push the design prompt through Claude Design, tweak the results, and get a design spec. When I have the frontier model do the planning, I have it read the implementation spec from before, along with the design spec's overview file.


When I do it this way, I've done A/B tests between Fable 5 and Sol, and the apps they wrote were basically identical. It's so much cheaper than the "let loose the subagent fleet!" form of context management.


I haven't even added any kind of frontier model validation cycle into this loop yet. Everyone keeps talking about a subagent flow in which the big boy reviews the work of the drones, but I've found that if it encodes its acceptance criteria well enough, they do a satisfactory job of it themselves.






reply










potus_kushner
5 hours ago
|
prev
|
next
[–]








this article is full of missing text like this:
"    of Opus at     of the cost,      the speed,     points over oneshot Flash."
is it just me or is that page using some brand new js feature or chromium-only hack?






reply










Bolwin
10 hours ago
|
prev
[–]








This is a lot of words to say "switch models instead of writing a plan file and starting a new session" which I do anyway.


That said, it takes me a while to reads plans and often I'll take a break, by when the cache has expired. At that point it may be better to start over






reply










fastball
10 hours ago
|
parent
[–]








I don't think that is the takeaway at all.






reply










Consider applying for YC's Fall 2026 batch!
Applications
are open till July 27.


Guidelines
|
FAQ
|
Lists
|
API
|
Security
|
Legal
|
Apply to YC
|
Contact




Search: