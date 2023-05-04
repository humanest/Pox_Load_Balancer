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
1. start controller by ```./pox.py log.level --DEBUG myLoadBalancer --servers_ip=10.0.0.1,10.0.0.2 --clients_ip=10.0.0.3,10.0.0.4,10.0.0.5,10.0.0.6 --policy=2```
with 2 servers h1 and h2, 4 clients h3, h4, h5, h6 and the policy is round robin
2. start mininet topology by ``` sudo python3 mininetTopo.py ```
3. In mininet, use ```dump``` to get the PID of each host and run ```sudo mnexec -a [PID] bash``` 
in new shell window to start the separate shell for each host.
4. In each host, run client.py and server.py