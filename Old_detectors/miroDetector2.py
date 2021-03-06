# Matt Whelan
# Here we will load up the trained SVM using HOG feature extraction. Then the
# adaptive threshold will be applied for finding a ROI, before attempting to
# classify the ROI

import numpy as np
import cv2
import os
import sys
import time

def imshow(img):
    cv2.imshow('image',img)
    cv2.waitKey(0)
    cv2.destroyAllWindows

class miroDetector:
    
    def __init__(self):        
        
        # Let's set up HOG and load the SVM data
        winSize = (64,64)
        blockSize = (16,16)
        blockStride = (8,8)
        cellSize = (8,8)
        nbins = 9
        derivAperture = 1
        winSigma = 4.
        histogramNormType = 0
        L2HysThreshold = 2.0000000000000001e-01
        gammaCorrection = 0
        nlevels = 64
        self.hog = cv2.HOGDescriptor(winSize,blockSize,blockStride,cellSize,nbins,derivAperture,winSigma,
                                histogramNormType,L2HysThreshold,gammaCorrection,nlevels)
        self.svm = cv2.ml.SVM_load('svm.dat')

    def detector(self,img):
        # cropping off the top third of the image
        img = img[80:239, 0:319]
        
        roi = self.ROI(img)
        
        # The SVM classifier will now be run on each ROI. The ROI is first set to a square
        # size, reduced (or increased) to size 64x64, then tested using HOG and SVM.
        detected = []
        for r in range(len(roi)):
            (x,y,w,h) = roi[r]
            winSize = 32
            while winSize < min(w,h):
                for x_win in range(x, x + w - winSize, 4):
                    for y_win in range(y, y + h - winSize, 4):
                        try:
                            win = img[y_win:(y_win+winSize), x_win:(x_win+winSize)]
                            img_roi = cv2.resize(win,(64,64))
                            hog_feature = np.transpose(self.hog.compute(img_roi)).astype(np.float32)
                            result = self.svm.predict(hog_feature)[1]
                            if result>0:
                                detected.append(((x_win,y_win,winSize),result))
                        except cv2.error:
                            pass
                winSize += 8
        if len(detected) == 0:
            print "No MiRo detected"
            sys.exit(0)
        #~ for det in detected:
            #~ (x_win,y_win,winSize) = det[0]
            #~ result = det[1]
            #~ cv2.rectangle(img, (x_win,y_win), (x_win+winSize,y_win+winSize), (255,0,0), 2)
            #~ if result==1:
                #~ print 'MiRo has been detected from the left side'
            #~ if result==2:
                #~ print 'MiRo has been detected from the right side'
            #~ if result==3:
                #~ print 'MiRo has been detected from the back side'
            #~ imshow(img)
            
        detectedZones = self.overlap(detected)
        self.displayZones(img,detectedZones)
        return detectedZones

    def ROI(self,img):
        # thresholding the standard image
        k = 0.5
        thresh_prop = 1.0
        img_grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean,stddev = cv2.meanStdDev(img_grey)
        while thresh_prop > 0.15:            
            thresh = mean*(1 + -k*(stddev/128 - 1))
            img_thresh = cv2.inRange(img_grey, thresh, 255)
            thresh_prop = float(cv2.countNonZero(img_thresh)) / (float(np.shape(img)[0]) * float(np.shape(img)[1]))
            #print k
            #print thresh_prop
            #imshow(img_thresh)
            k += 0.05
        _,contours,_ = cv2.findContours(img_thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        roi = []
        for c in contours:
            if cv2.contourArea(c) < 256:
                continue
            (x, y, w, h) = cv2.boundingRect(c)
            (x, y, w, h) = self.ROI_expand((x,y,w,h))
            roi.append((x,y,w,h))
        return roi
    
    def ROI_expand(self,(x,y,w,h)):
        
        w_new = int(w*1.5)
        h_new = int(h*1.5)
        x_new = x - (w_new - w)/2
        y_new = y - (h_new - h)/2
        if x_new >= 0:
            x = x_new
        if y_new >= 0:
            y = y_new
        return (x, y, w_new, h_new)
    
    def overlap(self,detected):
        # This method counts the number of overlapping detected zones, determines most likely orientation, 
        # and returns single detected regions with a count of the total number of detections per orientation
        
        x = []
        y = []
        win = []
        groups = np.zeros(len(detected))
        
        for det in detected:
            (x_win,y_win,winSize) = det[0]
            x.append(x_win)
            y.append(y_win)
            win.append(winSize)
        
        groups[0] = 1
        for i in range(len(detected)):
            for j in range(i+1,len(detected)):
                if i==j:
                    continue
                a1 = x[j] <= (x[i] + win[i]) and x[j] >= x[i]
                a2 = y[j] <= (y[i] + win[i]) and y[j] >= y[i]
                a3 = x[i] <= (x[j] + win[j]) and x[i] >= x[j]
                a4 = y[i] <= (y[j] + win[j]) and y[i] >= y[j]
                
                if a1 and (a2 or a4):
                    groups[j] = groups[i]
                elif a3 and (a2 or a4):
                    groups[j] = groups[i]
                elif groups[j] == 0:
                    groups[j] = max(groups) + 1
        
        no_groups = int(max(groups))
        groupRegions = np.zeros((no_groups,4))
        for i in range(len(groups)):            
            if groupRegions[int(groups[i]-1),3] == 0:
                groupRegions[int(groups[i]-1),:] = (x[i],y[i],x[i] + win[i],y[i] + win[i])
            else:
                if x[i] < groupRegions[int(groups[i]-1),0]:
                    groupRegions[int(groups[i]-1),0] = x[i]
                if y[i] < groupRegions[int(groups[i]-1),1]:
                    groupRegions[int(groups[i]-1),1] = y[i]
                if x[i] + win[i] > groupRegions[int(groups[i]-1),2]:
                    groupRegions[int(groups[i]-1),2] = x[i] + win[i]
                if y[i] + win[i] > groupRegions[int(groups[i]-1),3]:
                    groupRegions[int(groups[i]-1),3] = y[i] + win[i]
        
        noOrientations = np.zeros((no_groups,3)) # each row represents a group, and is organised as (noLSide, noRSide, noBack)
        for i in range(len(groups)):
            if detected[i][1] == 1.0:
                noOrientations[int(groups[i])-1,0] += 1
            if detected[i][1] == 2.0:
                noOrientations[int(groups[i]-1),1] += 1
            if detected[i][1] == 3.0:
                noOrientations[int(groups[i]-1),2] += 1
        
        detectedZones = np.zeros((no_groups,7))
        detectedZones[:,0:4] = groupRegions
        detectedZones[:,4:7] = noOrientations
        
        return detectedZones
                
    def displayZones(self, img, detectedZones):
        
        for zone in detectedZones:
            (xMin,yMin) = zone[0:2]
            (xMax,yMax) = zone[2:4]
            (xMin,yMin) = (int(xMin),int(yMin))
            (xMax,yMax) = (int(xMax),int(yMax))
            
            noLSide = zone[4]
            noRSide = zone[5]
            noBack = zone[6]
            total = noLSide + noRSide + noBack
            
            #~ LPerc = int(100 * noLSide / total)
            #~ RPerc = int(100 * noRSide / total)
            #~ BPerc = int(100 * noBack / total)
                        
            cv2.rectangle(img, (xMin,yMin), (xMax,yMax), (0,0,255), 2)
            cv2.putText(img, str(noLSide), (xMin,yMin), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(img, str(noRSide), (xMin,yMin+25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(img, str(noBack), (xMin,yMin+50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
            
            imshow(img)
        
if __name__ == "__main__":
    
    for arg in sys.argv[1:]:
        f = arg.find('=')
        if f == -1:
            key = arg
            val = ""
        else:
            key = arg[:f]
            val = arg[f+1:]    
        if key == "image_path":
            image = val
        else:
            print("argument \"image_path\" must be specified")
            sys.exit(0)
    img = cv2.imread(image)
    cv2.imshow('image',img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    if img is None:
        print("Invalid image location specified")
        sys.exit(0)
    t0 = time.time()
    miroDetector().detector(img)
    t1 = time.time()
    print t1 - t0
