# Pox_Load_Balancer

This is a repo for SDN final project.

How to commit your change?

1. Pull from master ```git checkout master```, ```git pull```
1. Start a new develop branch from master: ```git checkout -b your_branch_name```
    * If you want to use old one, just checkout to it: ```git checkout your_branch_name```, ```git rebase master```
2. Write some code
3. Commit the change: ```git add .```, ```git commit -m "describe this commit"```
4. Merge into master: ```git checkout master```, ```git pull```, ```git merge your_branch_name```, ```git push```

How to run the code?
1. modify the topology.in to decide the number of host and client you want to create.
2. create directory /tmp/server_status/ to store the log info.
2. start controller by ```./pox.py log.level --DEBUG Pox_Load_Balancer --policy=2``` and the policy is round robin
3. start mininet topology by ``` sudo python3 mininetTopo.py ```
