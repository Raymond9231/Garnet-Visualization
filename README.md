Raymond's modification:



I create a new logging method to track the movement of each tick(see processed.txt in ./Raymond's Experiments/ folder)



RI (ready to inject) global\_id, pack\_id, id,src, dest



SI (start injects) global\_id, pack\_id, id, ext\_link\_id



ST (start transmits) global\_id, pack\_id, id, int\_link\_id



DR (during transmits) global\_id, pack\_id, id, int\_link\_id



SE (start ejects) global\_id, pack\_id, id, ext\_link\_id



RR (router receives) global\_id, pack\_id, id, router\_id



For visualization, I'm figuring out the relationships between link id and router id

