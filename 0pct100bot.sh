gpio -g write 4 1
while :
do
    # ON
    gpio -g write 12 0
    gpio -g write 22 1
    gpio -g write 23 1

    # SLEEP
    sleep 10
done
