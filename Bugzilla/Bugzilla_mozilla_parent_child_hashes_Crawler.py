import requests
from datetime import datetime
#from prettytable import PrettyTable
from bs4 import BeautifulSoup
import logging
from logging import info
from time import strftime, localtime
import pyodbc
import traceback
import re
import time
import argparse

test_content = '''
# HG changeset patch
# User Marco Bonardo <mbonardo@mozilla.com>
# Date 1309853727 -7200
# Node ID 26cce0d3e1030a3ede35b55e257dcf1e36539153
# Parent  ed0f5032ff400a9865891f77042395313aa3c2a8# Parent  8df23f5d97091b393dfceb950275cacc24290f0e
Merge last green changeset from mozilla-inbound to mozilla-central

diff --git a/browser/base/content/browser-tabview.js b/browser/base/content/browser-tabview.js
--- a/browser/base/content/browser-tabview.js
+++ b/browser/base/content/browser-tabview.js
@@ -350,20 +350,18 @@ let TabView = {
         event.preventDefault();
 
         self._initFrame(function() {
           let groupItems = self._window.GroupItems;
           let tabItem = groupItems.getNextGroupItemTab(event.shiftKey);
           if (!tabItem)
             return;
 
-          // Switch to the new tab, and close the old group if it's now empty.
-          let oldGroupItem = groupItems.getActiveGroupItem();
+          // Switch to the new tab
           window.gBrowser.selectedTab = tabItem.tab;
-          oldGroupItem.closeIfEmpty();
         });
       }
     }, true);
   },
 
   // ----------
   // Prepares the tab view for undo close tab.
   prepareUndoCloseTab: function(blankTabToRemove) {
diff --git a/browser/base/content/tabview/drag.js b/browser/base/content/tabview/drag.js
--- a/browser/base/content/tabview/drag.js
+++ b/browser/base/content/tabview/drag.js
@@ -62,18 +62,17 @@ var resize = {
 // ----------
 // Constructor: Drag
 // Called to create a Drag in response to an <Item> draggable "start" event.
 // Note that it is also used partially during <Item>'s resizable method as well.
 //
 // Parameters:
 //   item - The <Item> being dragged
 //   event - The DOM event that kicks off the drag
-//   isFauxDrag - (boolean) true if a faux drag, which is used when simply snapping.
-function Drag(item, event, isFauxDrag) {
+function Drag(item, event) {
   Utils.assert(item && (item.isAnItem || item.isAFauxItem), 
       'must be an item, or at least a faux item');
 
   this.item = item;
   this.el = item.container;
   this.$el = iQ(this.el);
   this.parent = this.item.parent;
   this.startPosition = new Point(event.clientX, event.clientY);
@@ -277,28 +276,26 @@ Drag.prototype = {
   // Called in response to an <Item> draggable "stop" event.
   //
   // Parameters:
   //  immediately - bool for doing the pushAway immediately, without animation
   stop: function Drag_stop(immediately) {
     Trenches.hideGuides();
     this.item.isDragging = false;
 
-    if (this.parent && this.parent != this.item.parent &&
-       this.parent.isEmpty()) {
-      this.parent.close();
-    }
+    if (this.parent && this.parent != this.item.parent)
+      this.parent.closeIfEmpty();
 
     if (this.parent && this.parent.expanded)
       this.parent.arrange();
 
     if (this.item.parent)
       this.item.parent.arrange();
 
-    if (!this.item.parent) {
+    if (this.item.isAGroupItem) {
       this.item.setZ(drag.zIndex);
       drag.zIndex++;
 
       this.item.pushAway(immediately);
     }
 
     Trenches.disactivate();
   }
diff --git a/browser/base/content/tabview/groupitems.js b/browser/base/content/tabview/groupitems.js
--- a/browser/base/content/tabview/groupitems.js
+++ b/browser/base/content/tabview/groupitems.js
@@ -98,17 +98,17 @@ function GroupItem(listOfEls, options) {
   var rectToBe;
   if (options.bounds) {
     Utils.assert(Utils.isRect(options.bounds), "options.bounds must be a Rect");
     rectToBe = new Rect(options.bounds);
   }
 
   if (!rectToBe) {
     rectToBe = GroupItems.getBoundingBox(listOfEls);
-    rectToBe.inset(-30, -30);
+    rectToBe.inset(-42, -42);
   }
 
   var $container = options.container;
   let immediately = options.immediately || $container ? true : false;
   if (!$container) {
     $container = iQ('<div>')
       .addClass('groupItem')
       .css({position: 'absolute'})
@@ -270,16 +270,19 @@ function GroupItem(listOfEls, options) {
     this.setZ(drag.zIndex);
     drag.zIndex++; 
   } else
     // Calling snap will also trigger pushAway
     this.snap(immediately);
   if ($container)
     this.setBounds(rectToBe, immediately);
 
+  if (!options.immediately && listOfEls.length > 0)
+    $container.hide().fadeIn();
+
   this._inited = true;
   this.save();
 
   GroupItems.updateGroupCloseButtons();
 };
 
 // ----------
 GroupItem.prototype = Utils.extend(new Item(), new Subscribable(), {
@@ -715,28 +718,28 @@ GroupItem.prototype = Utils.extend(new I
   // ----------
   // Function: _makeClosestTabActive
   // Make the closest tab external to this group active.
   // Used when closing the group.
   _makeClosestTabActive: function GroupItem__makeClosestTabActive() {
     let closeCenter = this.getBounds().center();
     // Find closest tab to make active
     let closestTabItem = UI.getClosestTab(closeCenter);
-    UI.setActive(closestTabItem);
+    if (closestTabItem)
+      UI.setActive(closestTabItem);
   },
 
   // ----------
   // Function: closeIfEmpty
-  // Closes the group if it's empty, has no title, is closable, and
-  // autoclose is enabled (see pauseAutoclose()). Returns true if the close
-  // occurred and false otherwise.
-  closeIfEmpty: function() {
-    if (!this._children.length && !this.getTitle() &&
-        !GroupItems.getUnclosableGroupItemId() &&
-        !GroupItems._autoclosePaused) {
+  // Closes the group if it's empty, is closable, and autoclose is enabled
+  // (see pauseAutoclose()). Returns true if the close occurred and false
+  // otherwise.
+  closeIfEmpty: function GroupItem_closeIfEmpty() {
+    if (this.isEmpty() && !UI._closedLastVisibleTab &&
+        !GroupItems.getUnclosableGroupItemId() && !GroupItems._autoclosePaused) {
       this.close();
       return true;
     }
     return false;
   },
 
   // ----------
   // Function: _unhide
@@ -772,23 +775,22 @@ GroupItem.prototype = Utils.extend(new I
   // ----------
   // Function: closeHidden
   // Removes the group item, its children and its container.
   closeHidden: function GroupItem_closeHidden() {
     let self = this;
 
     this._cancelFadeAwayUndoButtonTimer();
 
-    // When the last non-empty groupItem is closed and there are no orphan or
+    // When the last non-empty groupItem is closed and there are no
     // pinned tabs then create a new group with a blank tab.
     let remainingGroups = GroupItems.groupItems.filter(function (groupItem) {
       return (groupItem != self && groupItem.getChildren().length);
     });
-    if (!gBrowser._numPinnedTabs && !GroupItems.getOrphanedTabs().length &&
-        !remainingGroups.length) {
+    if (!gBrowser._numPinnedTabs && !remainingGroups.length) {
       let emptyGroups = GroupItems.groupItems.filter(function (groupItem) {
         return (groupItem != self && !groupItem.getChildren().length);
       });
       let group = (emptyGroups.length ? emptyGroups[0] : GroupItems.newGroup());
       group.newTab(null, { closedLastTab: true });
     }
 
     this.destroy();
@@ -843,26 +845,27 @@ GroupItem.prototype = Utils.extend(new I
 
   // ----------
   // Function: _fadeAwayUndoButton
   // Fades away the undo button
   _fadeAwayUndoButton: function GroupItem__fadeAwayUdoButton() {
     let self = this;
 
     if (this.$undoContainer) {
-      // if there is one or more orphan tabs or there is more than one group 
-      // and other groupS are not empty, fade away the undo button.
-      let shouldFadeAway = GroupItems.getOrphanedTabs().length > 0;
-      
-      if (!shouldFadeAway && GroupItems.groupItems.length > 1) {
+      // if there is more than one group and other groups are not empty,
+      // fade away the undo button.
+      let shouldFadeAway = false;
+
+      if (GroupItems.groupItems.length > 1) {
         shouldFadeAway = 
           GroupItems.groupItems.some(function(groupItem) {
             return (groupItem != self && groupItem.getChildren().length > 0);
           });
       }
+
       if (shouldFadeAway) {
         self.$undoContainer.animate({
           color: "transparent",
           opacity: 0
         }, {
           duration: this._fadeAwayUndoButtonDuration,
           complete: function() { self.closeHidden(); }
         });
@@ -997,17 +1000,16 @@ GroupItem.prototype = Utils.extend(new I
         wasAlreadyInThisGroupItem = true;
       }
 
       // Insert the tab into the right position.
       var index = ("index" in options) ? options.index : this._children.length;
       this._children.splice(index, 0, item);
 
       item.setZ(this.getZ() + 1);
-      $el.addClass("tabInGroupItem");
 
       if (!wasAlreadyInThisGroupItem) {
         item.droppable(false);
         item.groupItemData = {};
 
         item.addSubscriber(this, "close", function() {
           let count = self._children.length;
           let dontArrange = self.expanded || !self.shouldStack(count);
@@ -1084,17 +1086,16 @@ GroupItem.prototype = Utils.extend(new I
       if (item == this._activeTab || !this._activeTab) {
         if (this._children.length > 0)
           this._activeTab = this._children[0];
         else
           this._activeTab = null;
       }
 
       item.setParent(null);
-      item.removeClass("tabInGroupItem");
       item.removeClass("stacked");
       item.isStacked = false;
       item.setHidden(false);
       item.removeClass("stack-trayed");
       item.setRotation(0);
 
       // Force tabItem resize if it's dragged out of a stacked groupItem.
       // The tabItems's title will be visible and that's why we need to
@@ -1105,17 +1106,17 @@ GroupItem.prototype = Utils.extend(new I
       item.droppable(true);
       item.removeSubscriber(this, "close");
 
       if (typeof item.setResizable == 'function')
         item.setResizable(true, options.immediately);
 
       // if a blank tab is selected while restoring a tab the blank tab gets
       // removed. we need to keep the group alive for the restored tab.
-      if (item.tab._tabViewTabIsRemovedAfterRestore)
+      if (item.isRemovedAfterRestore)
         options.dontClose = true;
 
       let closed = options.dontClose ? false : this.closeIfEmpty();
       if (closed)
         this._makeClosestTabActive();
       else if (!options.dontArrange) {
         this.arrange({animate: !options.immediately});
         this._unfreezeItemSize({dontArrange: true});
@@ -1854,17 +1855,16 @@ GroupItem.prototype = Utils.extend(new I
 // ##########
 // Class: GroupItems
 // Singleton for managing all <GroupItem>s.
 let GroupItems = {
   groupItems: [],
   nextID: 1,
   _inited: false,
   _activeGroupItem: null,
-  _activeOrphanTab: null,
   _cleanupFunctions: [],
   _arrangePaused: false,
   _arrangesPending: [],
   _removingHiddenGroups: false,
   _delayedModUpdates: [],
   _autoclosePaused: false,
   minGroupHeight: 110,
   minGroupWidth: 125,
@@ -2263,94 +2263,66 @@ let GroupItems = {
 
   // ----------
   // Function: newTab
   // Given a <TabItem>, files it in the appropriate groupItem.
   newTab: function GroupItems_newTab(tabItem, options) {
     let activeGroupItem = this.getActiveGroupItem();
 
     // 1. Active group
-    // 2. Active orphan
-    // 3. First visible non-app tab (that's not the tab in question), whether it's an
-    // orphan or not (make a new group if it's an orphan, add it to the group if it's
-    // not)
-    // 4. First group
-    // 5. First orphan that's not the tab in question
-    // 6. At this point there should be no groups or tabs (except for app tabs and the
+    // 2. First visible non-app tab (that's not the tab in question)
+    // 3. First group
+    // 4. At this point there should be no groups or tabs (except for app tabs and the
     // tab in question): make a new group
 
-    if (activeGroupItem) {
+    if (activeGroupItem && !activeGroupItem.hidden) {
       activeGroupItem.add(tabItem, options);
       return;
     }
 
-    let orphanTabItem = UI.getActiveOrphanTab();
-    if (!orphanTabItem) {
-      let targetGroupItem;
-      // find first visible non-app tab in the tabbar.
-      gBrowser.visibleTabs.some(function(tab) {
-        if (!tab.pinned && tab != tabItem.tab) {
-          if (tab._tabViewTabItem) {
-            if (!tab._tabViewTabItem.parent) {
-              // the first visible tab is an orphan tab, set the orphan tab, and 
-              // create a new group for orphan tab and new tabItem
-              orphanTabItem = tab._tabViewTabItem;
-            } else if (!tab._tabViewTabItem.parent.hidden) {
-              // the first visible tab belongs to a group, add the new tabItem to 
-              // that group
-              targetGroupItem = tab._tabViewTabItem.parent;
-            }
-          }
-          return true;
-        }
-        return false;
-      });
-
-      let visibleGroupItems;
-      if (!orphanTabItem) {
-        if (targetGroupItem) {
-          // add the new tabItem to the first group item
-          targetGroupItem.add(tabItem);
-          UI.setActive(targetGroupItem);
-          return;
-        } else {
-          // find the first visible group item
-          visibleGroupItems = this.groupItems.filter(function(groupItem) {
-            return (!groupItem.hidden);
-          });
-          if (visibleGroupItems.length > 0) {
-            visibleGroupItems[0].add(tabItem);
-            UI.setActive(visibleGroupItems[0]);
-            return;
+    let targetGroupItem;
+    // find first visible non-app tab in the tabbar.
+    gBrowser.visibleTabs.some(function(tab) {
+      if (!tab.pinned && tab != tabItem.tab) {
+        if (tab._tabViewTabItem) {
+          if (!tab._tabViewTabItem.parent && !tab._tabViewTabItem.parent.hidden) {
+            // the first visible tab belongs to a group, add the new tabItem to 
+            // that group
+            targetGroupItem = tab._tabViewTabItem.parent;
           }
         }
-        let orphanedTabs = this.getOrphanedTabs();
-        // set the orphan tab, and create a new group for orphan tab and 
-        // new tabItem
-        if (orphanedTabs.length > 0)
-          orphanTabItem = orphanedTabs[0];
+        return true;
+      }
+      return false;
+    });
+
+    let visibleGroupItems;
+    if (targetGroupItem) {
+      // add the new tabItem to the first group item
+      targetGroupItem.add(tabItem);
+      UI.setActive(targetGroupItem);
+      return;
+    } else {
+      // find the first visible group item
+      visibleGroupItems = this.groupItems.filter(function(groupItem) {
+        return (!groupItem.hidden);
+      });
+      if (visibleGroupItems.length > 0) {
+        visibleGroupItems[0].add(tabItem);
+        UI.setActive(visibleGroupItems[0]);
+        return;
       }
     }
 
-    // create new group for orphan tab and new tabItem
-    let tabItems;
-    let newGroupItemBounds;
-    // the orphan tab would be the same as tabItem when all tabs are app tabs
-    // and a new tab is created.
-    if (orphanTabItem && orphanTabItem.tab != tabItem.tab) {
-      newGroupItemBounds = orphanTabItem.getBounds();
-      tabItems = [orphanTabItem, tabItem];
-    } else {
-      tabItem.setPosition(60, 60, true);
-      newGroupItemBounds = tabItem.getBounds();
-      tabItems = [tabItem];
-    }
+    // create new group for the new tabItem
+    tabItem.setPosition(60, 60, true);
+    let newGroupItemBounds = tabItem.getBounds();
 
     newGroupItemBounds.inset(-40,-40);
-    let newGroupItem = new GroupItem(tabItems, { bounds: newGroupItemBounds });
+    let newGroupItem = new GroupItem([tabItem], { bounds: newGroupItemBounds });
     newGroupItem.snap();
     UI.setActive(newGroupItem);
   },
 
   // ----------
   // Function: getActiveGroupItem
   // Returns the active groupItem. Active means its tabs are
   // shown in the tab bar when not in the TabView interface.
@@ -2359,83 +2331,60 @@ let GroupItems = {
   },
 
   // ----------
   // Function: setActiveGroupItem
   // Sets the active groupItem, thereby showing only the relevant tabs and
   // setting the groupItem which will receive new tabs.
   //
   // Paramaters:
-  //  groupItem - the active <GroupItem> or <null> if no groupItem is active
-  //          (which means we have an orphaned tab selected)
+  //  groupItem - the active <GroupItem>
   setActiveGroupItem: function GroupItems_setActiveGroupItem(groupItem) {
+    Utils.assert(groupItem, "groupItem must be given");
+
     if (this._activeGroupItem)
       iQ(this._activeGroupItem.container).removeClass('activeGroupItem');
 
-    if (groupItem !== null) {
-      if (groupItem)
-        iQ(groupItem.container).addClass('activeGroupItem');
-    }
+    iQ(groupItem.container).addClass('activeGroupItem');
 
     this._activeGroupItem = groupItem;
     this._save();
   },
 
   // ----------
   // Function: _updateTabBar
-  // Hides and shows tabs in the tab bar based on the active groupItem or
-  // currently active orphan tabItem
+  // Hides and shows tabs in the tab bar based on the active groupItem
   _updateTabBar: function GroupItems__updateTabBar() {
     if (!window.UI)
       return; // called too soon
 
-    let activeOrphanTab;
-    if (!this._activeGroupItem) {
-      activeOrphanTab = UI.getActiveOrphanTab();
-      if (!activeOrphanTab) {
-        Utils.assert(false, "There must be something to show in the tab bar!");
-        return;
-      }
-    }
+    Utils.assert(this._activeGroupItem, "There must be something to show in the tab bar!");
 
-    let tabItems = this._activeGroupItem == null ?
-      [activeOrphanTab] : this._activeGroupItem._children;
+    let tabItems = this._activeGroupItem._children;
     gBrowser.showOnlyTheseTabs(tabItems.map(function(item) item.tab));
   },
 
   // ----------
   // Function: updateActiveGroupItemAndTabBar
   // Sets active TabItem and GroupItem, and updates tab bar appropriately.
   updateActiveGroupItemAndTabBar: function GroupItems_updateActiveGroupItemAndTabBar(tabItem) {
     Utils.assertThrow(tabItem && tabItem.isATabItem, "tabItem must be a TabItem");
 
     UI.setActive(tabItem);
     this._updateTabBar();
   },
 
   // ----------
-  // Function: getOrphanedTabs
-  // Returns an array of all tabs that aren't in a groupItem.
-  getOrphanedTabs: function GroupItems_getOrphanedTabs() {
-    var tabs = TabItems.getItems();
-    tabs = tabs.filter(function(tab) {
-      return tab.parent == null;
-    });
-    return tabs;
-  },
-
-  // ----------
   // Function: getNextGroupItemTab
   // Paramaters:
   //  reverse - the boolean indicates the direction to look for the next groupItem.
   // Returns the <tabItem>. If nothing is found, return null.
   getNextGroupItemTab: function GroupItems_getNextGroupItemTab(reverse) {
     var groupItems = Utils.copy(GroupItems.groupItems);
     var activeGroupItem = GroupItems.getActiveGroupItem();
-    var activeOrphanTab = UI.getActiveOrphanTab();
     var tabItem = null;
 
     if (reverse)
       groupItems = groupItems.reverse();
 
     if (!activeGroupItem) {
       if (groupItems.length > 0) {
         groupItems.some(function(groupItem) {
@@ -2479,21 +2428,16 @@ let GroupItems = {
           if (child) {
             tabItem = child;
             return true;
           }
         }
         return false;
       });
       if (!tabItem) {
-        var orphanedTabs = GroupItems.getOrphanedTabs();
-        if (orphanedTabs.length > 0)
-          tabItem = orphanedTabs[0];
-      }
-      if (!tabItem) {
         var secondGroupItems = groupItems.slice(0, currentIndex);
         secondGroupItems.some(function(groupItem) {
           if (!groupItem.hidden) {
             // restore the last active tab in the group
             let activeTab = groupItem.getActiveTab();
             if (activeTab) {
               tabItem = activeTab;
               return true;
@@ -2557,17 +2501,17 @@ let GroupItems = {
     } else {
       let pageBounds = Items.getPageBounds();
       pageBounds.inset(20, 20);
 
       let box = new Rect(pageBounds);
       box.width = 250;
       box.height = 200;
 
-      new GroupItem([ tab._tabViewTabItem ], { bounds: box });
+      new GroupItem([ tab._tabViewTabItem ], { bounds: box, immediately: true });
     }
 
     if (shouldUpdateTabBar)
       this._updateTabBar();
     else if (shouldShowTabView)
       UI.showTabView();
   },
 
diff --git a/browser/base/content/tabview/items.js b/browser/base/content/tabview/items.js
--- a/browser/base/content/tabview/items.js
+++ b/browser/base/content/tabview/items.js
@@ -159,19 +159,23 @@ Item.prototype = {
           this.parent._dropSpaceActive = true;
         drag.info = new Drag(this, e);
       },
       drag: function(e) {
         drag.info.drag(e);
       },
       stop: function() {
         drag.info.stop();
+
+        if (!this.isAGroupItem && !this.parent) {
+          new GroupItem([drag.info.$el], {focusTitle: true});
+          gTabView.firstUseExperienced = true;
+        }
+
         drag.info = null;
-        if (!this.isAGroupItem && !this.parent)
-          gTabView.firstUseExperienced = true;
       },
       // The minimum the mouse must move after mouseDown in order to move an 
       // item
       minDragDistance: 3
     };
 
     // ___ drop
     this.dropOptions = {
@@ -536,19 +540,17 @@ Item.prototype = {
   //
   // Parameters:
   //  immediately - bool for having the drag do the final positioning without animation
   snap: function Item_snap(immediately) {
     // make the snapping work with a wider range!
     var defaultRadius = Trenches.defaultRadius;
     Trenches.defaultRadius = 2 * defaultRadius; // bump up from 10 to 20!
 
-    var event = {startPosition:{}}; // faux event
-    var FauxDragInfo = new Drag(this, event, true);
-    // true == isFauxDrag
+    var FauxDragInfo = new Drag(this, {});
     FauxDragInfo.snap('none', false);
     FauxDragInfo.stop(immediately);
 
     Trenches.defaultRadius = defaultRadius;
   },
 
   // ----------
   // Function: draggable
diff --git a/browser/base/content/tabview/tabitems.js b/browser/base/content/tabview/tabitems.js
--- a/browser/base/content/tabview/tabitems.js
+++ b/browser/base/content/tabview/tabitems.js
@@ -107,79 +107,19 @@ function TabItem(tab, options) {
 
   this._lastTabUpdateTime = Date.now();
 
   // ___ superclass setup
   this._init(div);
 
   // ___ drag/drop
   // override dropOptions with custom tabitem methods
-  // This is mostly to support the phantom groupItems.
   this.dropOptions.drop = function(e) {
-    var $target = this.$container;
-    this.isDropTarget = false;
-
-    var phantom = $target.data("phantomGroupItem");
-
-    var groupItem = drag.info.item.parent;
-    if (groupItem) {
-      groupItem.add(drag.info.$el);
-    } else {
-      phantom.removeClass("phantom acceptsDrop");
-      let opts = {container:phantom, bounds:phantom.bounds(), focusTitle: true};
-      new GroupItem([$target, drag.info.$el], opts);
-    }
-  };
-
-  this.dropOptions.over = function(e) {
-    var $target = this.$container;
-    this.isDropTarget = true;
-
-    $target.removeClass("acceptsDrop");
-
-    var phantomMargin = 40;
-
-    var groupItemBounds = this.getBounds();
-    groupItemBounds.inset(-phantomMargin, -phantomMargin);
-
-    iQ(".phantom").remove();
-    var phantom = iQ("<div>")
-      .addClass("groupItem phantom acceptsDrop")
-      .css({
-        position: "absolute",
-        zIndex: -99
-      })
-      .css(groupItemBounds)
-      .hide()
-      .appendTo("body");
-
-    var defaultRadius = Trenches.defaultRadius;
-    // Extend the margin so that it covers the case where the target tab item
-    // is right next to a trench.
-    Trenches.defaultRadius = phantomMargin + 1;
-    var updatedBounds = drag.info.snapBounds(groupItemBounds,'none');
-    Trenches.defaultRadius = defaultRadius;
-
-    // Utils.log('updatedBounds:',updatedBounds);
-    if (updatedBounds)
-      phantom.css(updatedBounds);
-
-    phantom.fadeIn();
-
-    $target.data("phantomGroupItem", phantom);
-  };
-
-  this.dropOptions.out = function(e) {
-    this.isDropTarget = false;
-    var phantom = this.$container.data("phantomGroupItem");
-    if (phantom) {
-      phantom.fadeOut(function() {
-        iQ(this).remove();
-      });
-    }
+    let groupItem = drag.info.item.parent;
+    groupItem.add(drag.info.$el);
   };
 
   this.draggable();
 
   // ___ more div setup
   $div.mousedown(function(e) {
     if (!Utils.isRightClick(e))
       self.lastMouseDownTarget = e.target;
@@ -196,17 +136,16 @@ function TabItem(tab, options) {
       self.closedManually = true;
       self.close();
     } else {
       if (!Items.item(this).isDragging)
         self.zoomIn();
     }
   });
 
-  this.setResizable(true, options.immediately);
   this.droppable(true);
 
   TabItems.register(this);
 
   // ___ reconnect to data from Storage
   if (!TabItems.reconnectingPaused())
     this._reconnect();
 };
@@ -284,18 +223,16 @@ TabItem.prototype = Utils.extend(new Ite
     if (getImageData) { 
       if (this._cachedImageData)
         imageData = this._cachedImageData;
       else if (this.tabCanvas)
         imageData = this.tabCanvas.toImageData();
     }
 
     return {
-      bounds: this.getBounds(),
-      userSize: (Utils.isPoint(this.userSize) ? new Point(this.userSize) : null),
       url: this.tab.linkedBrowser.currentURI.spec,
       groupID: (this.parent ? this.parent.id : 0),
       imageData: imageData,
       title: getImageData && this.tab.label || null
     };
   },
 
   // ----------
@@ -343,57 +280,43 @@ TabItem.prototype = Utils.extend(new Ite
     };
     // getTabData returns the sessionstore contents, but passes
     // a callback to run when the thumbnail is finally loaded.
     tabData = Storage.getTabData(this.tab, imageDataCb);
     if (tabData && TabItems.storageSanity(tabData)) {
       if (self.parent)
         self.parent.remove(self, {immediately: true});
 
-      self.setBounds(tabData.bounds, true);
-
-      if (Utils.isPoint(tabData.userSize))
-        self.userSize = new Point(tabData.userSize);
+      let groupItem;
 
       if (tabData.groupID) {
-        var groupItem = GroupItems.groupItem(tabData.groupID);
-        if (groupItem) {
-          groupItem.add(self, {immediately: true});
-
-          // if it matches the selected tab or no active tab and the browser
-          // tab is hidden, the active group item would be set.
-          if (self.tab == gBrowser.selectedTab ||
-              (!GroupItems.getActiveGroupItem() && !self.tab.hidden))
-            UI.setActive(self.parent);
-        }
+        groupItem = GroupItems.groupItem(tabData.groupID);
       } else {
-        // When duplicating a non-blank orphaned tab, create a group including both of them.
-        // This prevents overlaid tabs in Tab View (only one tab appears to be there).
-        // In addition, as only one active orphaned tab is shown when Tab View is hidden
-        // and there are two tabs shown after the duplication, it also prevents
-        // the inactive tab to suddenly disappear when toggling Tab View twice.
-        //
-        // Fixes:
-        //   Bug 645653 - Middle-click on reload button to duplicate orphan tabs does not create a group
-        //   Bug 643119 - Ctrl+Drag to duplicate does not work for orphaned tabs
-        //   ... (and any other way of duplicating a non-blank orphaned tab).
-        if (GroupItems.getActiveGroupItem() == null)
-          GroupItems.newTab(self, {immediately: true});
+        groupItem = new GroupItem([], {immediately: true, bounds: tabData.bounds});
+      }
+
+      if (groupItem) {
+        groupItem.add(self, {immediately: true});
+
+        // if it matches the selected tab or no active tab and the browser
+        // tab is hidden, the active group item would be set.
+        if (self.tab == gBrowser.selectedTab ||
+            (!GroupItems.getActiveGroupItem() && !self.tab.hidden))
+          UI.setActive(self.parent);
       }
     } else {
-      // create tab by double click is handled in UI_init().
-      if (!UI.creatingNewOrphanTab)
-        GroupItems.newTab(self, {immediately: true});
+      // create tab group by double click is handled in UI_init().
+      GroupItems.newTab(self, {immediately: true});
     }
 
     self._reconnected = true;
     self.save();
     self._sendToSubscribers("reconnected");
   },
-  
+
   // ----------
   // Function: setHidden
   // Hide/unhide this item
   setHidden: function TabItem_setHidden(val) {
     if (val)
       this.addClass("tabHidden");
     else
       this.removeClass("tabHidden");
@@ -590,34 +513,16 @@ TabItem.prototype = Utils.extend(new Ite
   // ----------
   // Function: removeClass
   // Removes the specified CSS class from this item's container DOM element.
   removeClass: function TabItem_removeClass(className) {
     this.$container.removeClass(className);
   },
 
   // ----------
-  // Function: setResizable
-  // If value is true, makes this item resizable, otherwise non-resizable.
-  // Shows/hides a visible resize handle as appropriate.
-  setResizable: function TabItem_setResizable(value, immediately) {
-    var $resizer = iQ('.expander', this.container);
-
-    if (value) {
-      this.resizeOptions.minWidth = TabItems.minTabWidth;
-      this.resizeOptions.minHeight = TabItems.minTabHeight;
-      immediately ? $resizer.show() : $resizer.fadeIn();
-      this.resizable(true);
-    } else {
-      immediately ? $resizer.hide() : $resizer.fadeOut();
-      this.resizable(false);
-    }
-  },
-
-  // ----------
   // Function: makeActive
   // Updates this item to visually indicate that it's active.
   makeActive: function TabItem_makeActive() {
     this.$container.addClass("focus");
 
     if (this.parent)
       this.parent.setActiveTab(this);
   },
@@ -907,18 +812,17 @@ let TabItems = {
       return this._fragment;
 
     let div = document.createElement("div");
     div.classList.add("tab");
     div.innerHTML = "<div class='thumb'>" +
             "<img class='cached-thumb' style='display:none'/><canvas moz-opaque/></div>" +
             "<div class='favicon'><img/></div>" +
             "<span class='tab-title'>&nbsp;</span>" +
-            "<div class='close'></div>" +
-            "<div class='expander'></div>";
+            "<div class='close'></div>";
     this._fragment = document.createDocumentFragment();
     this._fragment.appendChild(div);
 
     return this._fragment;
   },
 
   // ----------
   // Function: isComplete
@@ -1068,19 +972,16 @@ let TabItems = {
   // Function: unlink
   // Takes in a xul:tab and destroys the TabItem associated with it. 
   unlink: function TabItems_unlink(tab) {
     try {
       Utils.assertThrow(tab, "tab");
       Utils.assertThrow(tab._tabViewTabItem, "should already be linked");
       // note that it's ok to unlink an app tab; see .handleTabUnpin
 
-      if (tab._tabViewTabItem == UI.getActiveOrphanTab())
-        UI.setActive(null, { onlyRemoveActiveTab: true });
-
       this.unregister(tab._tabViewTabItem);
       tab._tabViewTabItem._sendToSubscribers("close");
       tab._tabViewTabItem.$container.remove();
       tab._tabViewTabItem.removeTrenches();
       Items.unsquish(null, tab._tabViewTabItem);
 
       tab._tabViewTabItem.tab = null;
       tab._tabViewTabItem.tabCanvas.tab = null;
@@ -1260,25 +1161,19 @@ let TabItems = {
       item.save(saveImageData);
     });
   },
 
   // ----------
   // Function: storageSanity
   // Checks the specified data (as returned by TabItem.getStorageData or loaded from storage)
   // and returns true if it looks valid.
-  // TODO: check everything
+  // TODO: this is a stub, please implement
   storageSanity: function TabItems_storageSanity(data) {
-    var sane = true;
-    if (!Utils.isRect(data.bounds)) {
-      Utils.log('TabItems.storageSanity: bad bounds', data.bounds);
-      sane = false;
-    }
-
-    return sane;
+    return true;
   },
 
   // ----------
   // Function: getFontSizeFromWidth
   // Private method that returns the fontsize to use given the tab's width
   getFontSizeFromWidth: function TabItem_getFontSizeFromWidth(width) {
     let widthRange = new Range(0, TabItems.tabWidth);
     let proportion = widthRange.proportion(width - TabItems.tabItemPadding.x, true);
diff --git a/browser/base/content/tabview/trench.js b/browser/base/content/tabview/trench.js
--- a/browser/base/content/tabview/trench.js
+++ b/browser/base/content/tabview/trench.js
@@ -569,19 +569,17 @@ var Trenches = {
   // Activate all <Trench>es other than those projected by the current element.
   //
   // Parameters:
   //   element - (DOMElement) the DOM element of the Item being dragged or resized.
   activateOthersTrenches: function Trenches_activateOthersTrenches(element) {
     this.trenches.forEach(function(t) {
       if (t.el === element)
         return;
-      if (t.parentItem && (t.parentItem.isAFauxItem ||
-         t.parentItem.isDragging ||
-         t.parentItem.isDropTarget))
+      if (t.parentItem && (t.parentItem.isAFauxItem || t.parentItem.isDragging))
         return;
       t.active = true;
       t.calculateActiveRange();
       t.show(); // debug
     });
   },
 
   // ---------
@@ -629,17 +627,17 @@ var Trenches = {
     var updated = false;
     var updatedX = false;
     var updatedY = false;
 
     var snappedTrenches = {};
 
     for (var i in this.trenches) {
       var t = this.trenches[i];
-      if (!t.active || t.parentItem.isDropTarget)
+      if (!t.active)
         continue;
       // newRect will be a new rect, or false
       var newRect = t.rectOverlaps(rect,stationaryCorner,assumeConstantSize,keepProportional);
 
       if (newRect) { // if rectOverlaps returned an updated rect...
 
         if (assumeConstantSize && updatedX && updatedY)
           break;
diff --git a/browser/base/content/tabview/ui.js b/browser/base/content/tabview/ui.js
--- a/browser/base/content/tabview/ui.js
+++ b/browser/base/content/tabview/ui.js
@@ -134,20 +134,16 @@ let UI = {
   // Variable: _browserKeys
   // Used to keep track of allowed browser keys.
   _browserKeys: null,
 
   // Variable: ignoreKeypressForSearch
   // Used to prevent keypress being handled after quitting search mode.
   ignoreKeypressForSearch: false,
 
-  // Variable: creatingNewOrphanTab
-  // Used to keep track of whether we are creating a new oprhan tab or not.
-  creatingNewOrphanTab: false,
-
   // Variable: _lastOpenedTab
   // Used to keep track of the last opened tab.
   _lastOpenedTab: null,
 
   // ----------
   // Function: toString
   // Prints [UI] for debug use
   toString: function UI_toString() {
@@ -192,39 +188,32 @@ let UI = {
               element.blur();
           });
         }
         if (e.originalTarget.id == "content") {
           if (!Utils.isLeftClick(e)) {
             self._lastClick = 0;
             self._lastClickPositions = null;
           } else {
-            // Create an orphan tab on double click
+            // Create a group with one tab on double click
             if (Date.now() - self._lastClick <= self.DBLCLICK_INTERVAL && 
                 (self._lastClickPositions.x - self.DBLCLICK_OFFSET) <= e.clientX &&
                 (self._lastClickPositions.x + self.DBLCLICK_OFFSET) >= e.clientX &&
                 (self._lastClickPositions.y - self.DBLCLICK_OFFSET) <= e.clientY &&
                 (self._lastClickPositions.y + self.DBLCLICK_OFFSET) >= e.clientY) {
-              self.setActive(null);
-              self.creatingNewOrphanTab = true;
 
               let box =
                 new Rect(e.clientX - Math.floor(TabItems.tabWidth/2),
                          e.clientY - Math.floor(TabItems.tabHeight/2),
                          TabItems.tabWidth, TabItems.tabHeight);
-              let newTab =
-                gBrowser.loadOneTab("about:blank", { inBackground: false });
+              box.inset(-30, -30);
 
-              newTab._tabViewTabItem.setBounds(box, true);
-              newTab._tabViewTabItem.pushAway(true);
-              self.setActive(newTab._tabViewTabItem);
-
-              self.creatingNewOrphanTab = false;
-              // the bounds of tab item is set and we can zoom in now.
-              newTab._tabViewTabItem.zoomIn(true);
+              let opts = {immediately: true, bounds: box};
+              let groupItem = new GroupItem([], opts);
+              groupItem.newTab();
 
               self._lastClick = 0;
               self._lastClickPositions = null;
               gTabView.firstUseExperienced = true;
             } else {
               self._lastClick = Date.now();
               self._lastClickPositions = new Point(e.clientX, e.clientY);
               self._createGroupItemOnDrag(e);
@@ -418,56 +407,34 @@ let UI = {
           self._setActiveTab(null);
       });
 
       this._activeTab.makeActive();
     }
   },
 
   // ----------
-  // Function: getActiveOrphanTab
-  // Returns the currently active orphan tab as a <TabItem>
-  getActiveOrphanTab: function UI_getActiveOrphanTab() {
-    return (this._activeTab && !this._activeTab.parent) ? this._activeTab : null;
-  },
-
-  // ----------
   // Function: setActive
   // Sets the active tab item or group item
   // Parameters:
   //
   // options
   //  dontSetActiveTabInGroup bool for not setting active tab in group
-  //  onlyRemoveActiveGroup bool for removing active group
-  //  onlyRemoveActiveTab bool for removing active tab
   setActive: function UI_setActive(item, options) {
-    if (item) {
-      if (item.isATabItem) {
-        if (item.parent)
-          GroupItems.setActiveGroupItem(item.parent);
-        else
-          GroupItems.setActiveGroupItem(null);
-        this._setActiveTab(item);
-      } else {
-        GroupItems.setActiveGroupItem(item);
-        if (!options || !options.dontSetActiveTabInGroup) {
-          let activeTab = item.getActiveTab()
-          if (activeTab)
-            this._setActiveTab(activeTab);
-        }
-      }
+    Utils.assert(item, "item must be given");
+
+    if (item.isATabItem) {
+      GroupItems.setActiveGroupItem(item.parent);
+      this._setActiveTab(item);
     } else {
-      if (options) {
-        if (options.onlyRemoveActiveGroup)
-          GroupItems.setActiveGroupItem(null);
-        else if (options.onlyRemoveActiveTab)
-          this._setActiveTab(null);
-      } else {
-        GroupItems.setActiveGroupItem(null);
-        this._setActiveTab(null);
+      GroupItems.setActiveGroupItem(item);
+      if (!options || !options.dontSetActiveTabInGroup) {
+        let activeTab = item.getActiveTab()
+        if (activeTab)
+          this._setActiveTab(activeTab);
       }
     }
   },
 
   // ----------
   // Function: isTabViewVisible
   // Returns true if the TabView UI is currently shown.
   isTabViewVisible: function UI_isTabViewVisible() {
@@ -518,27 +485,16 @@ let UI = {
 #ifdef XP_MACOSX
     this.setTitlebarColors(true);
 #endif
     let event = document.createEvent("Events");
     event.initEvent("tabviewshown", true, false);
 
     Storage.saveVisibilityData(gWindow, "true");
 
-    // Close the active group if it was empty. This will happen when the
-    // user returns to Panorama after looking at an app tab, having
-    // closed all other tabs. (If the user is looking at an orphan tab, then
-    // there is no active group for the purposes of this check.)
-    let activeGroupItem = null;
-    if (!UI.getActiveOrphanTab()) {
-      activeGroupItem = GroupItems.getActiveGroupItem();
-      if (activeGroupItem && activeGroupItem.closeIfEmpty())
-        activeGroupItem = null;
-    }
-
     if (zoomOut && currentTab && currentTab._tabViewTabItem) {
       item = currentTab._tabViewTabItem;
       // If there was a previous currentTab we want to animate
       // its thumbnail (canvas) for the zoom out.
       // Note that we start the animation on the chrome thread.
 
       // Zoom out!
       item.zoomOut(function() {
@@ -551,17 +507,16 @@ let UI = {
         dispatchEvent(event);
 
         // Flush pending updates
         GroupItems.flushAppTabUpdates();
 
         TabItems.resumePainting();
       });
     } else {
-      self.setActive(null, { onlyRemoveActiveTab: true });
       dispatchEvent(event);
 
       // Flush pending updates
       GroupItems.flushAppTabUpdates();
 
       TabItems.resumePainting();
     }
 
@@ -731,17 +686,17 @@ let UI = {
     // TabOpen
     this._eventListeners.open = function(tab) {
       if (tab.ownerDocument.defaultView != gWindow)
         return;
 
       // if it's an app tab, add it to all the group items
       if (tab.pinned)
         GroupItems.addAppTab(tab);
-      else if (self.isTabViewVisible())
+      else if (self.isTabViewVisible() && !self._storageBusyCount)
         self._lastOpenedTab = tab;
     };
     
     // TabClose
     this._eventListeners.close = function(tab) {
       if (tab.ownerDocument.defaultView != gWindow)
         return;
 
@@ -873,18 +828,17 @@ let UI = {
   // Function: onTabSelect
   // Called when the user switches from one tab to another outside of the TabView UI.
   onTabSelect: function UI_onTabSelect(tab) {
     this._currentTab = tab;
 
     if (this.isTabViewVisible()) {
       if (!this.restoredClosedTab && this._lastOpenedTab == tab && 
         tab._tabViewTabItem) {
-        if (!this.creatingNewOrphanTab)
-          tab._tabViewTabItem.zoomIn(true);
+        tab._tabViewTabItem.zoomIn(true);
         this._lastOpenedTab = null;
         return;
       }
       if (this._closedLastVisibleTab ||
           (this._closedSelectedTabInTabView && !this.closedLastTabInTabView) ||
           this.restoredClosedTab) {
         if (this.restoredClosedTab) {
           // when the tab view UI is being displayed, update the thumb for the 
@@ -922,30 +876,30 @@ let UI = {
     // update the tab bar for the new tab's group
     if (tab && tab._tabViewTabItem) {
       if (!TabItems.reconnectingPaused()) {
         newItem = tab._tabViewTabItem;
         GroupItems.updateActiveGroupItemAndTabBar(newItem);
       }
     } else {
       // No tabItem; must be an app tab. Base the tab bar on the current group.
-      // If no current group or orphan tab, figure it out based on what's
-      // already in the tab bar.
-      if (!GroupItems.getActiveGroupItem() && !UI.getActiveOrphanTab()) {
+      // If no current group, figure it out based on what's already in the tab
+      // bar.
+      if (!GroupItems.getActiveGroupItem()) {
         for (let a = 0; a < gBrowser.tabs.length; a++) {
           let theTab = gBrowser.tabs[a];
           if (!theTab.pinned) {
             let tabItem = theTab._tabViewTabItem;
             this.setActive(tabItem.parent);
             break;
           }
         }
       }
 
-      if (GroupItems.getActiveGroupItem() || UI.getActiveOrphanTab())
+      if (GroupItems.getActiveGroupItem())
         GroupItems._updateTabBar();
     }
   },
 
   // ----------
   // Function: setReorderTabsOnHide
   // Sets the groupItem which the tab items' tabs should be re-ordered when
   // switching to the main browser UI.
@@ -984,17 +938,17 @@ let UI = {
 
   // ----------
   // Function: getClosestTab
   // Convenience function to get the next tab closest to the entered position
   getClosestTab: function UI_getClosestTab(tabCenter) {
     let cl = null;
     let clDist;
     TabItems.getItems().forEach(function (item) {
-      if (item.parent && item.parent.hidden)
+      if (!item.parent || item.parent.hidden)
         return;
       let testDist = tabCenter.distance(item.bounds.center());
       if (cl==null || testDist < clDist) {
         cl = item;
         clDist = testDist;
       }
     });
     return cl;
@@ -1229,17 +1183,16 @@ let UI = {
   // Function: _createGroupItemOnDrag
   // Called in response to a mousedown in empty space in the TabView UI;
   // creates a new groupItem based on the user's drag.
   _createGroupItemOnDrag: function UI__createGroupItemOnDrag(e) {
     const minSize = 60;
     const minMinSize = 15;
 
     let lastActiveGroupItem = GroupItems.getActiveGroupItem();
-    this.setActive(null, { onlyRemoveActiveGroup: true });
 
     var startPos = { x: e.clientX, y: e.clientY };
     var phantom = iQ("<div>")
       .addClass("groupItem phantom activeGroupItem dragRegion")
       .css({
         position: "absolute",
         zIndex: -1,
         cursor: "default"
@@ -1322,29 +1275,18 @@ let UI = {
 
     function finalize(e) {
       iQ(window).unbind("mousemove", updateSize);
       item.container.removeClass("dragRegion");
       dragOutInfo.stop();
       let box = item.getBounds();
       if (box.width > minMinSize && box.height > minMinSize &&
          (box.width > minSize || box.height > minSize)) {
-        var bounds = item.getBounds();
-
-        // Add all of the orphaned tabs that are contained inside the new groupItem
-        // to that groupItem.
-        var tabs = GroupItems.getOrphanedTabs();
-        var insideTabs = [];
-        for each(let tab in tabs) {
-          if (bounds.contains(tab.bounds))
-            insideTabs.push(tab);
-        }
-
-        let opts = {bounds: bounds, focusTitle: true};
-        let groupItem = new GroupItem(insideTabs, opts);
+        let opts = {bounds: item.getBounds(), focusTitle: true};
+        let groupItem = new GroupItem([], opts);
         self.setActive(groupItem);
         phantom.remove();
         dragOutInfo = null;
         gTabView.firstUseExperienced = true;
       } else {
         collapse();
       }
     }
@@ -1510,19 +1452,19 @@ let UI = {
       }
       hideSearch(null);
     }
 
     if (!zoomedIn) {
       let unhiddenGroups = GroupItems.groupItems.filter(function(groupItem) {
         return (!groupItem.hidden && groupItem.getChildren().length > 0);
       });
-      // no pinned tabs, no visible groups and no orphaned tabs: open a new
-      // group, a blank tab and return
-      if (!unhiddenGroups.length && !GroupItems.getOrphanedTabs().length) {
+      // no pinned tabs and no visible groups: open a new group. open a blank
+      // tab and return
+      if (!unhiddenGroups.length) {
         let emptyGroups = GroupItems.groupItems.filter(function (groupItem) {
           return (!groupItem.hidden && !groupItem.getChildren().length);
         });
         let group = (emptyGroups.length ? emptyGroups[0] : GroupItems.newGroup());
         if (!gBrowser._numPinnedTabs) {
           group.newTab(null, { closedLastTab: true });
           return;
         }
diff --git a/browser/base/content/test/browser_visibleTabs.js b/browser/base/content/test/browser_visibleTabs.js
--- a/browser/base/content/test/browser_visibleTabs.js
+++ b/browser/base/content/test/browser_visibleTabs.js
@@ -125,9 +125,12 @@ function test() {
   is(gBrowser.tabs.length, 2, "still have 2 open tabs");
 
   // Close the last visible tab and make sure we still get a visible tab
   gBrowser.removeTab(testTab);
   is(gBrowser.visibleTabs.length, 1, "only orig is left and visible");
   is(gBrowser.tabs.length, 1, "sanity check that it matches");
   is(gBrowser.selectedTab, origTab, "got the orig tab");
   is(origTab.hidden, false, "and it's not hidden -- visible!");
+
+  if (tabViewWindow)
+    tabViewWindow.GroupItems.groupItems[0].close();
 }
diff --git a/browser/base/content/test/tabview/Makefile.in b/browser/base/content/test/tabview/Makefile.in
--- a/browser/base/content/test/tabview/Makefile.in
+++ b/browser/base/content/test/tabview/Makefile.in
@@ -95,17 +95,16 @@ include $(topsrcdir)/config/rules.mk
                  browser_tabview_bug612470.js \
                  browser_tabview_bug613541.js \
                  browser_tabview_bug616729.js \
                  browser_tabview_bug616967.js \
                  browser_tabview_bug618816.js \
                  browser_tabview_bug618828.js \
                  browser_tabview_bug619937.js \
                  browser_tabview_bug622835.js \
-                 browser_tabview_bug622872.js \
                  browser_tabview_bug623768.js \
                  browser_tabview_bug624265.js \
                  browser_tabview_bug624692.js \
                  browser_tabview_bug624727.js \
                  browser_tabview_bug624847.js \
                  browser_tabview_bug624931.js \
                  browser_tabview_bug624953.js \
                  browser_tabview_bug625195.js \
@@ -125,45 +124,44 @@ include $(topsrcdir)/config/rules.mk
                  browser_tabview_bug629195.js \
                  browser_tabview_bug630102.js \
                  browser_tabview_bug630157.js \
                  browser_tabview_bug631662.js \
                  browser_tabview_bug631752.js \
                  browser_tabview_bug633788.js \
                  browser_tabview_bug634077.js \
                  browser_tabview_bug634085.js \
-                 browser_tabview_bug634158.js \
                  browser_tabview_bug634672.js \
                  browser_tabview_bug635696.js \
                  browser_tabview_bug640765.js \
                  browser_tabview_bug641802.js \
                  browser_tabview_bug642793.js \
                  browser_tabview_bug643392.js \
                  browser_tabview_bug644097.js \
-                 browser_tabview_bug645653.js \
                  browser_tabview_bug648882.js \
                  browser_tabview_bug649006.js \
                  browser_tabview_bug649307.js \
                  browser_tabview_bug649319.js \
                  browser_tabview_bug650573.js \
                  browser_tabview_bug651311.js \
+                 browser_tabview_bug654721.js \
                  browser_tabview_bug654941.js \
                  browser_tabview_bug655269.js \
                  browser_tabview_bug656778.js \
                  browser_tabview_bug656913.js \
                  browser_tabview_bug662266.js \
+                 browser_tabview_bug663421.js \
                  browser_tabview_bug665502.js \
                  browser_tabview_dragdrop.js \
                  browser_tabview_exit_button.js \
                  browser_tabview_expander.js \
                  browser_tabview_firstrun_pref.js \
                  browser_tabview_group.js \
                  browser_tabview_launch.js \
                  browser_tabview_multiwindow_search.js \
-                 browser_tabview_orphaned_tabs.js \
                  browser_tabview_privatebrowsing.js \
                  browser_tabview_rtl.js \
                  browser_tabview_search.js \
                  browser_tabview_snapping.js \
                  browser_tabview_startup_transitions.js \
                  browser_tabview_undo_group.js \
                  dummy_page.html \
                  head.js \
diff --git a/browser/base/content/test/tabview/browser_tabview_bug597360.js b/browser/base/content/test/tabview/browser_tabview_bug597360.js
--- a/browser/base/content/test/tabview/browser_tabview_bug597360.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug597360.js
@@ -1,40 +1,30 @@
 /* Any copyright is dedicated to the Public Domain.
    http://creativecommons.org/publicdomain/zero/1.0/ */
 
 function test() {
   waitForExplicitFinish();
 
-  window.addEventListener("tabviewshown", onTabViewWindowLoaded, false);
-  TabView.show();
-}
+  newWindowWithTabView(function (win) {
+    registerCleanupFunction(function () win.close());
 
-function onTabViewWindowLoaded() {
-  window.removeEventListener("tabviewshown", onTabViewWindowLoaded, false);
-
-  let contentWindow = document.getElementById("tab-view").contentWindow;
-  is(contentWindow.GroupItems.groupItems.length, 1, 
-     "There is one group item on startup");
+    let cw = win.TabView.getContentWindow();
+    let groupItems = cw.GroupItems.groupItems;
+    let groupItem = groupItems[0];
 
-  let groupItem = contentWindow.GroupItems.groupItems[0];
-  groupItem.addSubscriber(groupItem, "groupHidden", function() {
-    groupItem.removeSubscriber(groupItem, "groupHidden");
-
-    let onTabViewHidden = function() {
-      window.removeEventListener("tabviewhidden", onTabViewHidden, false);
+    is(groupItems.length, 1, "There is one group item on startup");
 
-      is(contentWindow.GroupItems.groupItems.length, 1, 
-         "There is still one group item");
-      isnot(groupItem.id, contentWindow.GroupItems.groupItems[0].id, 
+    whenTabViewIsHidden(function () {
+      is(groupItems.length, 1, "There is still one group item");
+      isnot(groupItem.id, groupItems[0].id, 
             "The initial group item is not the same as the final group item");
-      is(gBrowser.tabs.length, 1, "There is only one tab");
-      ok(!TabView.isVisible(), "Tab View is hidden");
+      is(win.gBrowser.tabs.length, 1, "There is only one tab");
 
       finish();
-    };
-    window.addEventListener("tabviewhidden", onTabViewHidden, false);
+    }, win);
 
-    // create a new tab
-    EventUtils.synthesizeKey("t", { accelKey: true });
+    hideGroupItem(groupItem, function () {
+      // create a new tab
+      EventUtils.synthesizeKey("t", { accelKey: true }, cw);
+    });
   });
-  groupItem.closeAll();
 }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug598600.js b/browser/base/content/test/tabview/browser_tabview_bug598600.js
--- a/browser/base/content/test/tabview/browser_tabview_bug598600.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug598600.js
@@ -53,20 +53,18 @@ function test() {
 
     // add a new tab.
     newWin.gBrowser.addTab();
     is(newWin.gBrowser.tabs.length, 3, "There are 3 browser tabs"); 
 
     let onTabViewShow = function() {
       newWin.removeEventListener("tabviewshown", onTabViewShow, false);
 
-      let contentWindow = newWin.document.getElementById("tab-view").contentWindow;
-
+      let contentWindow = newWin.TabView.getContentWindow();
       is(contentWindow.GroupItems.groupItems.length, 2, "Has two group items");
-      is(contentWindow.GroupItems.getOrphanedTabs().length, 0, "No orphan tabs");
 
       // clean up and finish
       newWin.close();
 
       finish();
     }
     newWin.addEventListener("tabviewshown", onTabViewShow, false);
     waitForFocus(function() { newWin.TabView.toggle(); });
diff --git a/browser/base/content/test/tabview/browser_tabview_bug604098.js b/browser/base/content/test/tabview/browser_tabview_bug604098.js
--- a/browser/base/content/test/tabview/browser_tabview_bug604098.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug604098.js
@@ -1,45 +1,37 @@
 /* Any copyright is dedicated to the Public Domain.
    http://creativecommons.org/publicdomain/zero/1.0/ */
 
-let originalTab;
-let orphanedTab;
 let contentWindow;
 let contentElement;
 
 function test() {
   waitForExplicitFinish();
 
   registerCleanupFunction(function() {
     if (gBrowser.tabs.length > 1)
       gBrowser.removeTab(gBrowser.tabs[1]);
     hideTabView(function() {});
   });
 
   showTabView(function() {
     contentWindow = TabView.getContentWindow();
     contentElement = contentWindow.document.getElementById("content");
-    originalTab = gBrowser.visibleTabs[0];
     test1();
   });
 }
 
 function test1() {
-  is(contentWindow.GroupItems.getOrphanedTabs().length, 0, "No orphaned tabs");
+  let groupItems = contentWindow.GroupItems.groupItems;
+  is(groupItems.length, 1, "there is one groupItem");
 
   whenTabViewIsHidden(function() {
-    showTabView(function() {
-      is(contentWindow.GroupItems.getOrphanedTabs().length, 1,
-         "An orphaned tab is created");
-      hideTabView(function() {
-        gBrowser.selectedTab = originalTab;
-        finish();
-      });
-    });
+    is(groupItems.length, 2, "there are two groupItems");
+    closeGroupItem(groupItems[1], finish);
   });
 
   // first click
   mouseClick(contentElement, 0);
   // second click
   mouseClick(contentElement, 0);
 }
 
diff --git a/browser/base/content/test/tabview/browser_tabview_bug607108.js b/browser/base/content/test/tabview/browser_tabview_bug607108.js
--- a/browser/base/content/test/tabview/browser_tabview_bug607108.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug607108.js
@@ -17,72 +17,70 @@ function test() {
     EventUtils.synthesizeMouse(target, 400, 100, {type: "mousemove"}, cw);
     EventUtils.synthesizeMouseAtCenter(target, {type: "mouseup"}, cw);
   };
 
   let testCreateGroup = function (callback) {
     let content = cw.document.getElementById("content");
 
     // drag to create a new group
-    EventUtils.synthesizeMouse(content, 350, 50, {type: "mousedown"}, cw);
+    EventUtils.synthesizeMouse(content, 400, 50, {type: "mousedown"}, cw);
     EventUtils.synthesizeMouse(content, 500, 250, {type: "mousemove"}, cw);
     EventUtils.synthesizeMouse(content, 500, 250, {type: "mouseup"}, cw);
 
+    assertNumberOfGroupItems(2);
+
     // enter a title for the new group
     EventUtils.synthesizeKey("t", {}, cw);
     EventUtils.synthesizeKey("VK_RETURN", {}, cw);
 
-    assertNumberOfGroupItems(2);
 
     let groupItem = cw.GroupItems.groupItems[1];
     is(groupItem.getTitle(), "t", "new groupItem's title is correct");
 
     groupItem.addSubscriber(groupItem, "close", function () {
       groupItem.removeSubscriber(groupItem, "close");
       executeSoon(callback);
     });
 
     groupItem.closeAll();
   };
 
-  let testDropOnOrphan = function (callback) {
+  let testDragOutOfGroup = function (callback) {
     assertNumberOfGroupItems(1);
 
     let groupItem = cw.GroupItems.groupItems[0];
     dragTabOutOfGroup(groupItem);
-    dragTabOutOfGroup(groupItem);
     assertNumberOfGroupItems(2);
 
     // enter a title for the new group
     EventUtils.synthesizeKey("t", {}, cw);
     EventUtils.synthesizeKey("VK_RETURN", {}, cw);
 
     groupItem = cw.GroupItems.groupItems[1];
     is(groupItem.getTitle(), "t", "new groupItem's title is correct");
     closeGroupItem(groupItem, callback);
   };
 
   let onLoad = function (win) {
     registerCleanupFunction(function () win.close());
 
     for (let i = 0; i < 2; i++)
-      win.gBrowser.loadOneTab("about:blank", {inBackground: true});
+      win.gBrowser.addTab();
   };
 
   let onShow = function (win) {
     cw = win.TabView.getContentWindow();
     assertNumberOfGroupItems(1);
 
     let groupItem = cw.GroupItems.groupItems[0];
     groupItem.setSize(200, 600, true);
 
     waitForFocus(function () {
       testCreateGroup(function () {
-        testDropOnOrphan(function () {
-          waitForFocus(finish);
-        });
+        testDragOutOfGroup(finish);
       });
     }, cw);
   };
 
   waitForExplicitFinish();
   newWindowWithTabView(onShow, onLoad);
 }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug612470.js b/browser/base/content/test/tabview/browser_tabview_bug612470.js
--- a/browser/base/content/test/tabview/browser_tabview_bug612470.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug612470.js
@@ -15,34 +15,32 @@ function test() {
 
   let onShow = function () {
     cw = win.TabView.getContentWindow();
     is(cw.GroupItems.groupItems.length, 1, "There's only one group");
 
     groupItem = createEmptyGroupItem(cw, 200, 200, 20);
     cw.UI.setActive(groupItem);
 
-    executeSoon(function () hideTabView(onHide, win));
+    whenTabViewIsHidden(onHide, win);
+    cw.UI.goToTab(win.gBrowser.tabs[0]);
   };
 
   let onHide = function () {
     let tab = win.gBrowser.loadOneTab("about:blank", {inBackground: true});
     is(groupItem.getChildren().length, 1, "One tab is in the new group");
 
     executeSoon(function () {
       is(win.gBrowser.visibleTabs.length, 2, "There are two tabs displayed");
       win.gBrowser.removeTab(tab);
 
       is(groupItem.getChildren().length, 0, "No tabs are in the new group");
       is(win.gBrowser.visibleTabs.length, 1, "There is one tab displayed");
       is(cw.GroupItems.groupItems.length, 2, "There are two groups still");
 
-      showTabView(function () {
-        is(cw.GroupItems.groupItems.length, 1, "There is now only one group");
-        waitForFocus(finish);
-      }, win);
+      finish();
     });
   };
 
   waitForExplicitFinish();
 
   newWindowWithTabView(onShow, onLoad);
 }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug613541.js b/browser/base/content/test/tabview/browser_tabview_bug613541.js
--- a/browser/base/content/test/tabview/browser_tabview_bug613541.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug613541.js
@@ -201,71 +201,16 @@ function test() {
         assertGroupItemExists(groupItem);
         assertGroupItemRemoved(newGroupItem);
         gBrowser.unpinTab(gBrowser.selectedTab);
         next();
       });
     });
   }
 
-  // setup: 1 orphan tab
-  // action: exit panorama
-  // expected: nothing should happen
-  let testOrphanTab1 = function () {
-    let groupItem = getGroupItem(0);
-    let tabItem = groupItem.getChild(0);
-    groupItem.remove(tabItem);
-
-    hideTabView(function () {
-      assertNumberOfGroupItems(0);
-      createGroupItem().add(tabItem);
-      next();
-    });
-  }
-
-  // setup: 1 orphan tab, 1 non-empty group
-  // action: close the group
-  // expected: nothing should happen
-  let testOrphanTab2 = function () {
-    let groupItem = getGroupItem(0);
-    let tabItem = groupItem.getChild(0);
-    groupItem.remove(tabItem);
-
-    assertNumberOfGroupItems(0);
-    let newGroupItem = createGroupItem(1);
-    assertNumberOfGroupItems(1);
-
-    closeGroupItem(newGroupItem, function () {
-      assertNumberOfGroupItems(0);
-      createGroupItem().add(tabItem);
-      hideTabView(next);
-    });
-  }
-
-  // setup: 1 orphan tab, 1 non-empty group
-  // action: hide the group, exit panorama
-  // expected: nothing should happen
-  let testOrphanTab3 = function () {
-    let groupItem = getGroupItem(0);
-    let tabItem = groupItem.getChild(0);
-    groupItem.remove(tabItem);
-
-    assertNumberOfGroupItems(0);
-    let newGroupItem = createGroupItem(1);
-    assertNumberOfGroupItems(1);
-
-    hideGroupItem(newGroupItem, function () {
-      hideTabView(function () {
-        assertNumberOfGroupItems(0);
-        createGroupItem().add(tabItem);
-        next();
-      });
-    });
-  }
-
   // setup: 1 non-empty group, 1 empty group
   // action: close non-empty group
   // expected: empty group is re-used, new tab is created and zoomed into
   let testEmptyGroup1 = function () {
     let groupItem = getGroupItem(0);
     let newGroupItem = createGroupItem(0);
     assertNumberOfGroupItems(2);
 
@@ -338,20 +283,16 @@ function test() {
   tests.push({name: 'testNonEmptyGroup1', func: testNonEmptyGroup1});
   tests.push({name: 'testNonEmptyGroup2', func: testNonEmptyGroup2});
 
   tests.push({name: 'testPinnedTab1', func: testPinnedTab1});
   tests.push({name: 'testPinnedTab2', func: testPinnedTab2});
   tests.push({name: 'testPinnedTab3', func: testPinnedTab3});
   tests.push({name: 'testPinnedTab4', func: testPinnedTab4});
 
-  tests.push({name: 'testOrphanTab1', func: testOrphanTab1});
-  tests.push({name: 'testOrphanTab2', func: testOrphanTab2});
-  tests.push({name: 'testOrphanTab3', func: testOrphanTab3});
-
   tests.push({name: 'testEmptyGroup1', func: testEmptyGroup1});
   tests.push({name: 'testEmptyGroup2', func: testEmptyGroup2});
 
   tests.push({name: 'testHiddenGroup1', func: testHiddenGroup1});
   tests.push({name: 'testHiddenGroup2', func: testHiddenGroup2}),
 
   waitForExplicitFinish();
 
diff --git a/browser/base/content/test/tabview/browser_tabview_bug622872.js b/browser/base/content/test/tabview/browser_tabview_bug622872.js
deleted file mode 100644
--- a/browser/base/content/test/tabview/browser_tabview_bug622872.js
+++ /dev/null
@@ -1,118 +0,0 @@
-/* Any copyright is dedicated to the Public Domain.
-   http://creativecommons.org/publicdomain/zero/1.0/ */
-
-function test() {
-  waitForExplicitFinish();
-  newWindowWithTabView(part1);
-}
-
-// PART 1:
-// 1. Create a new tab (called newTab)
-// 2. Orphan it. Activate this orphan tab.
-// 3. Zoom into it.
-function part1(win) {
-  ok(win.TabView.isVisible(), "Tab View is visible");
-
-  let contentWindow = win.document.getElementById("tab-view").contentWindow;
-  is(win.gBrowser.tabs.length, 1, "In the beginning, there was one tab.");
-  let [originalTab] = win.gBrowser.visibleTabs;
-  let originalGroup = contentWindow.GroupItems.getActiveGroupItem();
-  ok(originalGroup.getChildren().some(function(child) {
-    return child == originalTab._tabViewTabItem;
-  }),"The current active group is the one with the original tab in it.");
-
-  // Create a new tab and orphan it
-  let newTab = win.gBrowser.loadOneTab("about:mozilla", {inBackground: true});
-
-  let newTabItem = newTab._tabViewTabItem;
-  ok(originalGroup.getChildren().some(function(child) child == newTabItem),"The new tab was made in the current group");
-  contentWindow.GroupItems.getActiveGroupItem().remove(newTabItem);
-  ok(!originalGroup.getChildren().some(function(child) child == newTabItem),"The new tab was orphaned");
-  newTabItem.pushAway();
-  // activate this tab item
-  contentWindow.UI.setActive(newTabItem);
-
-  // PART 2: close this orphan tab (newTab)
-  let part2 = function part2() {
-    win.removeEventListener("tabviewhidden", part2, false);
-
-    is(win.gBrowser.selectedTab, newTab, "We zoomed into that new tab.");
-    ok(!win.TabView.isVisible(), "Tab View is hidden, because we're looking at the new tab");
-
-    newTab.addEventListener("TabClose", function() {
-      newTab.removeEventListener("TabClose", arguments.callee, false);
-
-      win.addEventListener("tabviewshown", part3, false);
-      executeSoon(function() { win.TabView.toggle(); });
-    }, false);
-    win.gBrowser.removeTab(newTab);
-  }
-
-  let secondNewTab;
-  // PART 3: now back in Panorama, open a new tab via the "new tab" menu item (or equivalent)
-  // We call this secondNewTab.
-  let part3 = function part3() {
-    win.removeEventListener("tabviewshown", part3, false);
-
-    ok(win.TabView.isVisible(), "Tab View is visible.");
-
-    is(win.gBrowser.tabs.length, 1, "Only one tab again.");
-    is(win.gBrowser.tabs[0], originalTab, "That one tab is the original tab.");
-
-    let groupItems = contentWindow.GroupItems.groupItems;
-    is(groupItems.length, 1, "Only one group");
-
-    ok(!contentWindow.UI.getActiveOrphanTab(), "There is no active orphan tab.");
-    ok(win.TabView.isVisible(), "Tab View is visible.");
-  
-    whenTabViewIsHidden(part4, win);
-    win.document.getElementById("cmd_newNavigatorTab").doCommand();
-  }
-
-  // PART 4: verify it opened in the original group, and go back into Panorama
-  let part4 = function part4() {
-    ok(!win.TabView.isVisible(), "Tab View is hidden");
-
-    is(win.gBrowser.tabs.length, 2, "There are two tabs total now.");
-    is(win.gBrowser.visibleTabs.length, 2, "We're looking at both of them.");
-
-    let foundOriginalTab = false;
-    // we can't use forEach because win.gBrowser.tabs is only array-like.
-    for (let i = 0; i < win.gBrowser.tabs.length; i++) {
-      let tab = win.gBrowser.tabs[i];
-      if (tab === originalTab)
-        foundOriginalTab = true;
-      else
-        secondNewTab = tab;
-    }
-    ok(foundOriginalTab, "One of those tabs is the original tab.");
-    ok(secondNewTab, "We found another tab... this is secondNewTab");
-
-    is(win.gBrowser.selectedTab, secondNewTab, "This second new tab is what we're looking at.");
-
-    win.addEventListener("tabviewshown", part5, false);
-    win.TabView.toggle();
-  }
-
-  // PART 5: make sure we only have one group with both tabs now, and finish.
-  let part5 = function part5() {
-    win.removeEventListener("tabviewshown", part5, false);
-
-    is(win.gBrowser.tabs.length, 2, "There are of course still two tabs.");
-
-    let groupItems = contentWindow.GroupItems.groupItems;
-    is(groupItems.length, 1, "There is one group now");
-    is(groupItems[0], originalGroup, "It's the original group.");
-    is(originalGroup.getChildren().length, 2, "It has two children.");
-
-    // finish!
-    win.close();
-    finish();
-  }
-
-  // Okay, all set up now. Let's get this party started!
-  afterAllTabItemsUpdated(function() {
-    win.addEventListener("tabviewhidden", part2, false);
-    win.TabView.toggle();
-  }, win);
-}
diff --git a/browser/base/content/test/tabview/browser_tabview_bug624265.js b/browser/base/content/test/tabview/browser_tabview_bug624265.js
--- a/browser/base/content/test/tabview/browser_tabview_bug624265.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug624265.js
@@ -114,17 +114,18 @@ function test() {
     gBrowser.selectedTab = gBrowser.loadOneTab('http://mochi.test:8888/#3', {inBackground: true});
     gBrowser.loadOneTab('http://mochi.test:8888/#4', {inBackground: true});
 
     afterAllTabsLoaded(function () {
       assertNumberOfVisibleTabs(2);
 
       enterAndLeavePrivateBrowsing(function () {
         assertNumberOfVisibleTabs(2);
-        next();
+        gBrowser.selectedTab = gBrowser.tabs[0];
+        closeGroupItem(cw.GroupItems.groupItems[1], next);
       });
     });
   }
 
   waitForExplicitFinish();
 
   // tests for #624265
   tests.push(testUndoCloseTabs);
diff --git a/browser/base/content/test/tabview/browser_tabview_bug625424.js b/browser/base/content/test/tabview/browser_tabview_bug625424.js
--- a/browser/base/content/test/tabview/browser_tabview_bug625424.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug625424.js
@@ -4,86 +4,71 @@
 function test() {
   let win;
   let cw;
 
   let getGroupItem = function (index) {
     return cw.GroupItems.groupItems[index];
   }
 
-  let createOrphan = function (callback) {
-    let tab = win.gBrowser.loadOneTab('about:blank', {inBackground: true});
-    afterAllTabsLoaded(function () {
-      let tabItem = tab._tabViewTabItem;
-      tabItem.parent.remove(tabItem);
-      callback(tabItem);
-    });
-  }
-
-  let hideGroupItem = function (groupItem, callback) {
-    groupItem.addSubscriber(groupItem, 'groupHidden', function () {
-      groupItem.removeSubscriber(groupItem, 'groupHidden');
-      callback();
-    });
-    groupItem.closeAll();
-  }
-
   let newWindow = function (test) {
     newWindowWithTabView(function (tvwin) {
       registerCleanupFunction(function () {
         if (!tvwin.closed)
           tvwin.close();
       });
 
       win = tvwin;
       cw = win.TabView.getContentWindow();
+
+      // setup group items
+      getGroupItem(0).setSize(200, 200, true);
+      createGroupItemWithBlankTabs(win, 200, 200, 300, 1);
+
       test();
     });
   }
 
   let assertNumberOfTabsInGroupItem = function (groupItem, numTabs) {
     is(groupItem.getChildren().length, numTabs,
         'there are ' + numTabs + ' tabs in this groupItem');
   }
 
   let testDragOnHiddenGroup = function () {
-    createOrphan(function (orphan) {
-      let groupItem = getGroupItem(0);
-      hideGroupItem(groupItem, function () {
-        let drag = orphan.container;
-        let drop = groupItem.$undoContainer[0];
-
-        assertNumberOfTabsInGroupItem(groupItem, 1);
-
-        EventUtils.synthesizeMouseAtCenter(drag, {type: 'mousedown'}, cw);
-        EventUtils.synthesizeMouseAtCenter(drop, {type: 'mousemove'}, cw);
-        EventUtils.synthesizeMouseAtCenter(drop, {type: 'mouseup'}, cw);
+    let groupItem = getGroupItem(1);
 
-        assertNumberOfTabsInGroupItem(groupItem, 1);
-
-        win.close();
-        newWindow(testDragOnVisibleGroup);
-      });
-    });
-  }
-
-  let testDragOnVisibleGroup = function () {
-    createOrphan(function (orphan) {
-      let groupItem = getGroupItem(0);
-      let drag = orphan.container;
-      let drop = groupItem.container;
+    hideGroupItem(groupItem, function () {
+      let drag = groupItem.getChild(0).container;
+      let drop = groupItem.$undoContainer[0];
 
       assertNumberOfTabsInGroupItem(groupItem, 1);
 
       EventUtils.synthesizeMouseAtCenter(drag, {type: 'mousedown'}, cw);
       EventUtils.synthesizeMouseAtCenter(drop, {type: 'mousemove'}, cw);
       EventUtils.synthesizeMouseAtCenter(drop, {type: 'mouseup'}, cw);
 
-      assertNumberOfTabsInGroupItem(groupItem, 2);
+      assertNumberOfTabsInGroupItem(groupItem, 1);
 
       win.close();
-      finish();
+      newWindow(testDragOnVisibleGroup);
     });
   }
 
+  let testDragOnVisibleGroup = function () {
+    let groupItem = getGroupItem(0);
+    let drag = getGroupItem(1).getChild(0).container;
+    let drop = groupItem.container;
+
+    assertNumberOfTabsInGroupItem(groupItem, 1);
+
+    EventUtils.synthesizeMouseAtCenter(drag, {type: 'mousedown'}, cw);
+    EventUtils.synthesizeMouseAtCenter(drop, {type: 'mousemove'}, cw);
+    EventUtils.synthesizeMouseAtCenter(drop, {type: 'mouseup'}, cw);
+
+    assertNumberOfTabsInGroupItem(groupItem, 2);
+
+    win.close();
+    finish();
+  }
+
   waitForExplicitFinish();
   newWindow(testDragOnHiddenGroup);
 }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug631752.js b/browser/base/content/test/tabview/browser_tabview_bug631752.js
--- a/browser/base/content/test/tabview/browser_tabview_bug631752.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug631752.js
@@ -28,50 +28,58 @@ function test() {
       EventUtils.synthesizeMouse(doc, x, 100, {type: "mousemove"}, cw);
     ok(aspectRange.contains(getTabItemAspect(tabItem)), "tabItem's aspect is correct");
 
     ok(!groupItem.getBounds().intersects(tabItem.getBounds()), "tabItem was moved out of group bounds");
     ok(!tabItem.parent, "tabItem is orphaned");
 
     EventUtils.synthesizeMouseAtCenter(container, {type: "mouseup"}, cw);
     ok(aspectRange.contains(getTabItemAspect(tabItem)), "tabItem's aspect is correct");
-
-    tabItem.close();
   }
 
   let testDragOutOfStackedGroup = function () {
     dragTabItem();
-    testDragOutOfExpandedStackedGroup();
+
+    let secondGroup = cw.GroupItems.groupItems[1];
+    closeGroupItem(secondGroup, testDragOutOfExpandedStackedGroup);
   }
 
   let testDragOutOfExpandedStackedGroup = function () {
     groupItem.addSubscriber(groupItem, "expanded", function () {
       groupItem.removeSubscriber(groupItem, "expanded");
+      dragTabItem();
+    });
 
-      dragTabItem();
-      closeGroupItem(groupItem, function () hideTabView(finishTest));
+    groupItem.addSubscriber(groupItem, "collapsed", function () {
+      groupItem.removeSubscriber(groupItem, "collapsed");
+
+      let secondGroup = cw.GroupItems.groupItems[1];
+      closeGroupItem(secondGroup, function () hideTabView(finishTest));
     });
 
     groupItem.expand();
   }
 
   let finishTest = function () {
     is(cw.GroupItems.groupItems.length, 1, "there is one groupItem");
     is(gBrowser.tabs.length, 1, "there is one tab");
     ok(!TabView.isVisible(), "tabview is hidden");
 
     finish();
   }
 
   waitForExplicitFinish();
 
   newWindowWithTabView(function (win) {
-    registerCleanupFunction(function () {
-      if (!win.closed)
-        win.close();
-    });
+    registerCleanupFunction(function () win.close());
 
     cw = win.TabView.getContentWindow();
-    groupItem = createGroupItemWithBlankTabs(win, 200, 200, 10, 10);
+
+    groupItem = cw.GroupItems.groupItems[0];
+    groupItem.setSize(200, 200, true);
 
+    for (let i = 0; i < 9; i++)
+      win.gBrowser.addTab();
+
+    ok(groupItem.isStacked(), "groupItem is stacked");
     testDragOutOfStackedGroup();
   });
 }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug634158.js b/browser/base/content/test/tabview/browser_tabview_bug634158.js
deleted file mode 100644
--- a/browser/base/content/test/tabview/browser_tabview_bug634158.js
+++ /dev/null
@@ -1,31 +0,0 @@
-/* Any copyright is dedicated to the Public Domain.
-   http://creativecommons.org/publicdomain/zero/1.0/ */
-
-function test() {
-  waitForExplicitFinish();
-
-  newWindowWithTabView(function (win) {
-    registerCleanupFunction(function () {
-      if (!win.closed)
-        win.close();
-    });
-
-    let tabItem = win.gBrowser.tabs[0]._tabViewTabItem;
-    tabItem.parent.remove(tabItem);
-
-    let cw = win.TabView.getContentWindow();
-    let container = cw.iQ(tabItem.container);
-    let expander = cw.iQ('.expander', container);
-
-    let bounds = container.bounds();
-    let halfWidth = bounds.width / 2;
-    let halfHeight = bounds.height / 2;
-
-    let rect = new cw.Rect(bounds.left + halfWidth, bounds.top + halfHeight,
-                        halfWidth, halfHeight);
-    ok(rect.contains(expander.bounds()), "expander is in the tabItem's bottom-right corner");
-
-    win.close();
-    finish();
-  });
-}
diff --git a/browser/base/content/test/tabview/browser_tabview_bug635696.js b/browser/base/content/test/tabview/browser_tabview_bug635696.js
--- a/browser/base/content/test/tabview/browser_tabview_bug635696.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug635696.js
@@ -12,40 +12,26 @@ function test() {
       let groupItem = cw.GroupItems.groupItem(groupItemId);
       if (groupItem)
         groupItem.close();
     });
 
     return groupItem;
   }
 
-  let createOrphan = function () {
-    let tab = gBrowser.loadOneTab('about:blank', {inBackground: true});
-    registerCleanupFunction(function () {
-      if (gBrowser.tabs.length > 1)
-        gBrowser.removeTab(gBrowser.tabs[1])
-    });
-
-    let tabItem = tab._tabViewTabItem;
-    tabItem.parent.remove(tabItem);
-
-    return tabItem;
-  }
-
   let testSingleGroupItem = function () {
     let groupItem = cw.GroupItems.groupItems[0];
     is(cw.GroupItems.getActiveGroupItem(), groupItem, "groupItem is active");
 
     let tabItem = groupItem.getChild(0);
     is(cw.UI.getActiveTab(), tabItem, "tabItem is active");
 
     hideGroupItem(groupItem, function () {
-      is(cw.GroupItems.getActiveGroupItem(), null, "groupItem is not active");
       unhideGroupItem(groupItem, function () {
-        is(cw.GroupItems.getActiveGroupItem(), groupItem, "groupItem is active again");
+        is(cw.GroupItems.getActiveGroupItem(), groupItem, "groupItem is still active");
         is(cw.UI.getActiveTab(), tabItem, "tabItem is still active");
         next();
       });
     });
   }
 
   let testTwoGroupItems = function () {
     let groupItem = cw.GroupItems.groupItems[0];
@@ -58,32 +44,17 @@ function test() {
       is(cw.UI.getActiveTab(), tabItem2, "tabItem2 is active");
       unhideGroupItem(groupItem, function () {
         cw.UI.setActive(tabItem);
         closeGroupItem(groupItem2, next);
       });
     });
   }
 
-  let testOrphanTab = function () {
-    let groupItem = cw.GroupItems.groupItems[0];
-    let tabItem = groupItem.getChild(0);
-    let tabItem2 = createOrphan();
-
-    hideGroupItem(groupItem, function () {
-      is(cw.UI.getActiveTab(), tabItem2, "tabItem2 is active");
-      unhideGroupItem(groupItem, function () {
-        cw.UI.setActive(tabItem);
-        tabItem2.close();
-        next();
-      });
-    });
-  }
-
-  let tests = [testSingleGroupItem, testTwoGroupItems, testOrphanTab];
+  let tests = [testSingleGroupItem, testTwoGroupItems];
 
   let next = function () {
     let test = tests.shift();
     if (test)
       test();
     else
       hideTabView(finishTest);
   }
diff --git a/browser/base/content/test/tabview/browser_tabview_bug643392.js b/browser/base/content/test/tabview/browser_tabview_bug643392.js
--- a/browser/base/content/test/tabview/browser_tabview_bug643392.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug643392.js
@@ -1,13 +1,11 @@
 /* Any copyright is dedicated to the Public Domain.
    http://creativecommons.org/publicdomain/zero/1.0/ */
 
-const ss = Cc["@mozilla.org/browser/sessionstore;1"].getService(Ci.nsISessionStore);
-
 let state = {
   windows: [{
     tabs: [{
       entries: [{ url: "about:home" }],
       hidden: true,
       extData: {"tabview-tab": '{"url":"about:home","groupID":1,"bounds":{"left":20,"top":20,"width":20,"height":20}}'}
     },{
       entries: [{ url: "about:home" }],
diff --git a/browser/base/content/test/tabview/browser_tabview_bug645653.js b/browser/base/content/test/tabview/browser_tabview_bug645653.js
deleted file mode 100644
--- a/browser/base/content/test/tabview/browser_tabview_bug645653.js
+++ /dev/null
@@ -1,83 +0,0 @@
-/* Any copyright is dedicated to the Public Domain.
-   http://creativecommons.org/publicdomain/zero/1.0/ */
-
-/* Orphans a non-blank tab, duplicates it and checks whether a new group is created with two tabs.
- * The original one should be the first tab of the new group.
- *
- * This prevents overlaid tabs in Tab View (only one tab appears to be there).
- * In addition, as only one active orphaned tab is shown when Tab View is hidden
- * and there are two tabs shown after the duplication, it also prevents
- * the inactive tab to suddenly disappear when toggling Tab View twice.
- *
- * Covers:
- *   Bug 645653 - Middle-click on reload button to duplicate orphan tabs does not create a group
- *   Bug 643119 - Ctrl+Drag to duplicate does not work for orphaned tabs
- *   ... (and any other way of duplicating a non-blank orphaned tab).
- *
- * See tabitems.js::_reconnect() for the fix.
- *
- * Miguel Ojeda <miguel.ojeda.sandonis@gmail.com>
- */
-
-function loadedAboutMozilla(tab) {
-  return tab.linkedBrowser.contentDocument.getElementById('moztext');
-}
-
-function test() {
-  waitForExplicitFinish();
-  showTabView(function() {
-    ok(TabView.isVisible(), "Tab View is visible");
-
-    let contentWindow = TabView.getContentWindow();
-    is(contentWindow.GroupItems.groupItems.length, 1, "There is one group item on startup.");
-
-    let originalGroupItem = contentWindow.GroupItems.groupItems[0];
-    is(originalGroupItem.getChildren().length, 1, "There is one tab item in that group.");
-
-    let originalTabItem = originalGroupItem.getChild(0);
-    ok(originalTabItem, "The tabitem has been found.");
-
-    // close the group => orphan the tab
-    originalGroupItem.close();
-    contentWindow.UI.setActive(originalGroupItem);
-    is(contentWindow.GroupItems.groupItems.length, 0, "There are not any groups now.");
-
-    ok(TabView.isVisible(), "Tab View is still shown.");
-
-    hideTabView(function() {
-      ok(!TabView.isVisible(), "Tab View is not shown anymore.");
-
-      // load a non-blank page
-      loadURI('about:mozilla');
-
-      afterAllTabsLoaded(function() {
-        ok(loadedAboutMozilla(originalTabItem.tab), "The original tab loaded about:mozilla.");
-
-        // duplicate it
-        duplicateTabIn(originalTabItem.tab, "tabshift");
-
-        afterAllTabsLoaded(function() {
-          // check
-          is(gBrowser.selectedTab, originalTabItem.tab, "The selected tab is the original one.");
-          is(contentWindow.GroupItems.groupItems.length, 1, "There is one group item again.");
-          let groupItem = contentWindow.GroupItems.groupItems[0];
-          is(groupItem.getChildren().length, 2, "There are two tab items in that group.");
-          is(originalTabItem, groupItem.getChild(0), "The first tab item in the group is the original one.");
-          let otherTab = groupItem.getChild(1);
-          ok(loadedAboutMozilla(otherTab.tab), "The other tab loaded about:mozilla.");
-
-          // clean up
-          gBrowser.removeTab(otherTab.tab);
-          is(contentWindow.GroupItems.groupItems.length, 1, "There is one group item after closing the second tab.");
-          is(groupItem.getChildren().length, 1, "There is only one tab item after closing the second tab.");
-          is(originalTabItem, groupItem.getChild(0), "The first tab item in the group is still the original one.");
-          loadURI("about:blank");
-          afterAllTabsLoaded(function() {
-            finish();
-          });
-        });
-      });
-    });
-  });
-}
-
diff --git a/browser/base/content/test/tabview/browser_tabview_bug649319.js b/browser/base/content/test/tabview/browser_tabview_bug649319.js
--- a/browser/base/content/test/tabview/browser_tabview_bug649319.js
+++ b/browser/base/content/test/tabview/browser_tabview_bug649319.js
@@ -48,30 +48,20 @@ function testScenarios(win) {
   // resize group
   cw.UI.setActive(groupItem);
   let tabItem = groupItem2.getChild(2);
   groupItem2.setActiveTab(tabItem);
   simulateDragDrop(groupItem2.$resizer[0]);
   is(cw.GroupItems.getActiveGroupItem(), groupItem2, "second groupItem is active");
   is(cw.UI.getActiveTab(), tabItem, "second groupItem's third tab is active");
 
-  // create orphan
+  // drag tab out of group
   tabItem = groupItem2.getChild(0);
   dragOutOfGroup(tabItem.container);
-
-  // move orphan
-  cw.UI.setActive(groupItem2);
-  simulateDragDrop(tabItem.container);
-  assertActiveOrphan(tabItem);
-
-  // resize orphan
-  cw.UI.setActive(groupItem2);
-  let $resizer = cw.iQ('.iq-resizable-handle', tabItem.container);
-  simulateDragDrop($resizer[0]);
-  assertActiveOrphan(tabItem);
+  is(cw.UI.getActiveTab(), tabItem, "the dragged tab is active");
 
   // drag back into group
   dragIntoGroup(tabItem.container);
   cw.UI.setActive(groupItem);
   cw.UI.setActive(groupItem2);
   is(cw.UI.getActiveTab(), tabItem, "the dropped tab is active");
 
   // hide + unhide groupItem
diff --git a/browser/base/content/test/tabview/browser_tabview_bug654721.js b/browser/base/content/test/tabview/browser_tabview_bug654721.js
new file mode 100644
--- /dev/null
+++ b/browser/base/content/test/tabview/browser_tabview_bug654721.js
@@ -0,0 +1,63 @@
+/* Any copyright is dedicated to the Public Domain.
+   http://creativecommons.org/publicdomain/zero/1.0/ */
+
+let state = {
+  windows: [{
+    tabs: [{
+      entries: [{ url: "about:home" }],
+      hidden: true,
+      extData: {"tabview-tab": '{"url":"about:home","groupID":1,"bounds":{"left":20,"top":20,"width":20,"height":20}}'}
+    },{
+      entries: [{ url: "about:home" }],
+      hidden: false,
+      // this is an existing orphan tab from a previous Fx version and we want
+      // to make sure this gets transformed into a group
+      extData: {"tabview-tab": '{"url":"about:home","groupID":0,"bounds":{"left":300,"top":300,"width":200,"height":200}}'},
+    }],
+    selected: 2,
+    extData: {
+      "tabview-groups": '{"nextID":3,"activeGroupId":1}',
+      "tabview-group":
+        '{"1":{"bounds":{"left":20,"top":20,"width":200,"height":200},"id":1}}'
+    }
+  }]
+};
+
+function test() {
+  waitForExplicitFinish();
+
+  newWindowWithState(state, function (win) {
+    registerCleanupFunction(function () win.close());
+
+    showTabView(function () {
+      let cw = win.TabView.getContentWindow();
+      let groupItems = cw.GroupItems.groupItems;
+      is(groupItems.length, 2, "two groupItems");
+
+      let [group1, group2] = groupItems;
+
+      let bounds1 = new cw.Rect(20, 20, 200, 200);
+      ok(bounds1.equals(group1.getBounds()), "bounds for group1 are correct");
+
+      let bounds2 = new cw.Rect(300, 300, 200, 200);
+      ok(bounds2.equals(group2.getBounds()), "bounds for group2 are correct");
+
+      cw.UI.setActive(group2);
+      win.gBrowser.loadOneTab("about:blank", {inBackground: true});
+
+      let tabItem = group2.getChild(0);
+      let target = tabItem.container;
+
+      EventUtils.synthesizeMouse(target, 10, 10, {type: 'mousedown'}, cw);
+      EventUtils.synthesizeMouse(target, 20, -200, {type: 'mousemove'}, cw);
+      EventUtils.synthesizeMouse(target, 10, 10, {type: 'mouseup'}, cw);
+
+      is(groupItems.length, 3, "three groupItems");
+
+      let latestGroup = groupItems[groupItems.length - 1];
+      is(tabItem, latestGroup.getChild(0), "dragged tab has its own groupItem");
+
+      finish();
+    }, win);
+  });
+}
diff --git a/browser/base/content/test/tabview/browser_tabview_bug663421.js b/browser/base/content/test/tabview/browser_tabview_bug663421.js
new file mode 100644
--- /dev/null
+++ b/browser/base/content/test/tabview/browser_tabview_bug663421.js
@@ -0,0 +1,88 @@
+/* Any copyright is dedicated to the Public Domain.
+   http://creativecommons.org/publicdomain/zero/1.0/ */
+
+function test() {
+  let win, cw, groupItem;
+
+  function checkNumberOfGroupItems(num) {
+    is(cw.GroupItems.groupItems.length, num, "there are " + num + " groupItems");
+  }
+
+  function next() {
+    if (tests.length)
+      tests.shift()();
+    else
+      finish();
+  }
+
+  // Empty groups should not be closed when toggling Panorama on and off.
+  function test1() {
+    hideTabView(function () {
+      showTabView(function () {
+        checkNumberOfGroupItems(2);
+        next();
+      }, win);
+    }, win);
+  }
+
+  // Groups should not be closed when their last tab is closed outside of Panorama.
+  function test2() {
+    whenTabViewIsHidden(function () {
+      whenTabViewIsShown(function () {
+        checkNumberOfGroupItems(2);
+        next();
+      }, win);
+
+      win.gBrowser.removeTab(win.gBrowser.selectedTab);
+    }, win);
+
+    groupItem.newTab();
+  }
+
+  // Groups should be closed when their last tab is closed.
+  function test3() {
+    whenTabViewIsHidden(function () {
+      showTabView(function () {
+        let tab = win.gBrowser.tabs[1];
+        tab._tabViewTabItem.close();
+        checkNumberOfGroupItems(1);
+        next();
+      }, win);
+    }, win);
+
+    win.gBrowser.addTab();
+  }
+
+  // Groups should be closed when their last tab is dragged out.
+  function test4() {
+    groupItem = createGroupItemWithBlankTabs(win, 200, 200, 20, 1);
+    checkNumberOfGroupItems(2);
+
+    let tab = win.gBrowser.tabs[1];
+    let target = tab._tabViewTabItem.container;
+
+    waitForFocus(function () {
+      EventUtils.synthesizeMouseAtCenter(target, {type: "mousedown"}, cw);
+      EventUtils.synthesizeMouse(target, 600, 5, {type: "mousemove"}, cw);
+      EventUtils.synthesizeMouse(target, 600, 5, {type: "mouseup"}, cw);
+
+      checkNumberOfGroupItems(2);
+      next();
+    }, win);
+  }
+
+  let tests = [test1, test2, test3, test4];
+
+  waitForExplicitFinish();
+
+  newWindowWithTabView(function (aWin) {
+    registerCleanupFunction(function () aWin.close());
+
+    win = aWin;
+    cw = win.TabView.getContentWindow();
+    groupItem = createEmptyGroupItem(cw, 200, 200, 20);
+
+    checkNumberOfGroupItems(2);
+    next();
+  });
+}
diff --git a/browser/base/content/test/tabview/browser_tabview_firstrun_pref.js b/browser/base/content/test/tabview/browser_tabview_firstrun_pref.js
--- a/browser/base/content/test/tabview/browser_tabview_firstrun_pref.js
+++ b/browser/base/content/test/tabview/browser_tabview_firstrun_pref.js
@@ -35,34 +35,27 @@ function checkFirstRun(win) {
   
   // Welcome tab disabled by bug 626754. To be fixed via bug 626926.
   is(win.gBrowser.tabs.length, 1, "There should be one tab");
   
   let groupItems = contentWindow.GroupItems.groupItems;
   is(groupItems.length, 1, "There should be one group");
   is(groupItems[0].getChildren().length, 1, "...with one child");
 
-  let orphanTabCount = contentWindow.GroupItems.getOrphanedTabs().length;
-  // Welcome tab disabled by bug 626754. To be fixed via bug 626926.
-  is(orphanTabCount, 0, "There should also be no orphaned tabs");
-
   ok(!experienced(), "we're not experienced");
 }
 
 function checkNotFirstRun(win) {
   let contentWindow = win.document.getElementById("tab-view").contentWindow;
   
   is(win.gBrowser.tabs.length, 1, "There should be one tab");
   
   let groupItems = contentWindow.GroupItems.groupItems;
   is(groupItems.length, 1, "There should be one group");
   is(groupItems[0].getChildren().length, 1, "...with one child");
-
-  let orphanTabCount = contentWindow.GroupItems.getOrphanedTabs().length;
-  is(orphanTabCount, 0, "There should also be no orphaned tabs");
 }
 
 function endGame() {
   ok(!TabView.isVisible(), "Main window TabView is still hidden");
   ok(experienced(), "should finish as experienced");
 
   prefsBranch.setBoolPref("experienced_first_run", originalPrefState);
 
diff --git a/browser/base/content/test/tabview/browser_tabview_orphaned_tabs.js b/browser/base/content/test/tabview/browser_tabview_orphaned_tabs.js
deleted file mode 100644
--- a/browser/base/content/test/tabview/browser_tabview_orphaned_tabs.js
+++ /dev/null
@@ -1,81 +0,0 @@
-/* Any copyright is dedicated to the Public Domain.
-   http://creativecommons.org/publicdomain/zero/1.0/ */
-
-let tabOne;
-let newWin;
-
-function test() {
-  waitForExplicitFinish();
-
-  newWindowWithTabView(onTabViewWindowLoaded, function(win) {
-    newWin = win;
-    tabOne = newWin.gBrowser.addTab();
-  });
-}
-
-function onTabViewWindowLoaded() {
-  newWin.removeEventListener("tabviewshown", onTabViewWindowLoaded, false);
-
-  ok(newWin.TabView.isVisible(), "Tab View is visible");
-
-  let contentWindow = newWin.document.getElementById("tab-view").contentWindow;
-
-  // 1) the tab should belong to a group, and no orphan tabs
-  ok(tabOne._tabViewTabItem.parent, "Tab one belongs to a group");
-  is(contentWindow.GroupItems.getOrphanedTabs().length, 0, "No orphaned tabs");
-
-  // 2) create a group, add a blank tab 
-  let groupItem = createEmptyGroupItem(contentWindow, 300, 300, 200);
-
-  let onTabViewHidden = function() {
-    newWin.removeEventListener("tabviewhidden", onTabViewHidden, false);
-
-    // 3) the new group item should have one child and no orphan tab
-    is(groupItem.getChildren().length, 1, "The group item has an item");
-    is(contentWindow.GroupItems.getOrphanedTabs().length, 0, "No orphaned tabs");
-    
-    let checkAndFinish = function() {
-      // 4) check existence of stored group data for tab before finishing
-      let tabData = contentWindow.Storage.getTabData(tabItem.tab, function () {});
-      ok(tabData && contentWindow.TabItems.storageSanity(tabData) && tabData.groupID, 
-         "Tab two has stored group data");
-
-      // clean up and finish the test
-      newWin.gBrowser.removeTab(tabOne);
-      newWin.gBrowser.removeTab(tabItem.tab);
-      whenWindowObservesOnce(newWin, "domwindowclosed", function() {
-        finish();
-      });
-      newWin.close();
-    };
-    let tabItem = groupItem.getChild(0);
-    // the item may not be connected so subscriber would be used in that case.
-    if (tabItem._reconnected) {
-      checkAndFinish();
-    } else {
-      tabItem.addSubscriber(tabItem, "reconnected", function() {
-        tabItem.removeSubscriber(tabItem, "reconnected");
-        checkAndFinish();
-      });
-    }
-  };
-  newWin.addEventListener("tabviewhidden", onTabViewHidden, false);
-
-  // click on the + button
-  let newTabButton = groupItem.container.getElementsByClassName("newTabButton");
-  ok(newTabButton[0], "New tab button exists");
-
-  EventUtils.sendMouseEvent({ type: "click" }, newTabButton[0], contentWindow);
-}
-
-function whenWindowObservesOnce(win, topic, callback) {
-  let windowWatcher = 
-    Cc["@mozilla.org/embedcomp/window-watcher;1"].getService(Ci.nsIWindowWatcher);
-  function windowObserver(subject, topicName, aData) {
-    if (win == subject.QueryInterface(Ci.nsIDOMWindow) && topic == topicName) {
-      windowWatcher.unregisterNotification(windowObserver);
-      callback();
-    }
-  }
-  windowWatcher.registerNotification(windowObserver);
-}
diff --git a/browser/base/content/test/tabview/head.js b/browser/base/content/test/tabview/head.js
--- a/browser/base/content/test/tabview/head.js
+++ b/browser/base/content/test/tabview/head.js
@@ -76,29 +76,23 @@ function afterAllTabItemsUpdated(callbac
 
 // ---------
 function newWindowWithTabView(shownCallback, loadCallback, width, height) {
   let winWidth = width || 800;
   let winHeight = height || 800;
   let win = window.openDialog(getBrowserURL(), "_blank",
                               "chrome,all,dialog=no,height=" + winHeight +
                               ",width=" + winWidth);
-  let onLoad = function() {
-    win.removeEventListener("load", onLoad, false);
+
+  whenWindowLoaded(win, function () {
     if (typeof loadCallback == "function")
       loadCallback(win);
 
-    let onShown = function() {
-      win.removeEventListener("tabviewshown", onShown, false);
-      shownCallback(win);
-    };
-    win.addEventListener("tabviewshown", onShown, false);
-    win.TabView.toggle();
-  }
-  win.addEventListener("load", onLoad, false);
+    showTabView(function () shownCallback(win), win);
+  });
 }
 
 // ----------
 function afterAllTabsLoaded(callback, win) {
   const TAB_STATE_NEEDS_RESTORE = 1;
 
   win = win || window;
 
@@ -187,61 +181,61 @@ function whenTabViewIsShown(callback, wi
     callback();
   }, false);
 }
 
 // ----------
 function showSearch(callback, win) {
   win = win || window;
 
-  let contentWindow = win.document.getElementById("tab-view").contentWindow;
+  let contentWindow = win.TabView.getContentWindow();
   if (contentWindow.isSearchEnabled()) {
     callback();
     return;
   }
 
   whenSearchIsEnabled(callback, win);
   contentWindow.performSearch();
 }
 
 // ----------
 function hideSearch(callback, win) {
   win = win || window;
 
-  let contentWindow = win.document.getElementById("tab-view").contentWindow;
+  let contentWindow = win.TabView.getContentWindow();
   if (!contentWindow.isSearchEnabled()) {
     callback();
     return;
   }
 
   whenSearchIsDisabled(callback, win);
   contentWindow.hideSearch();
 }
 
 // ----------
 function whenSearchIsEnabled(callback, win) {
   win = win || window;
 
-  let contentWindow = win.document.getElementById("tab-view").contentWindow;
+  let contentWindow = win.TabView.getContentWindow();
   if (contentWindow.isSearchEnabled()) {
     callback();
     return;
   }
 
   contentWindow.addEventListener("tabviewsearchenabled", function () {
     contentWindow.removeEventListener("tabviewsearchenabled", arguments.callee, false);
     callback();
   }, false);
 }
 
 // ----------
 function whenSearchIsDisabled(callback, win) {
   win = win || window;
 
-  let contentWindow = win.document.getElementById("tab-view").contentWindow;
+  let contentWindow = win.TabView.getContentWindow();
   if (!contentWindow.isSearchEnabled()) {
     callback();
     return;
   }
 
   contentWindow.addEventListener("tabviewsearchdisabled", function () {
     contentWindow.removeEventListener("tabviewsearchdisabled", arguments.callee, false);
     callback();
diff --git a/browser/themes/gnomestripe/browser/tabview/tabview.css b/browser/themes/gnomestripe/browser/tabview/tabview.css
--- a/browser/themes/gnomestripe/browser/tabview/tabview.css
+++ b/browser/themes/gnomestripe/browser/tabview/tabview.css
@@ -8,27 +8,23 @@ body {
   background-color: window;
   background-image: -moz-linear-gradient(rgba(0,0,0,0.1),rgba(0,0,0,.2));
 }
 
 /* Tabs
 ----------------------------------*/
 
 .tab {
+  margin: 4px;
   padding-top: 4px;
   -moz-padding-end: 6px;
   padding-bottom: 6px;
   -moz-padding-start: 4px;
   background-color: #D7D7D7;
   border-radius: 0.4em;
-  box-shadow: 0 1px 0 #FFFFFF inset,
-              0 -1px 1px rgba(255, 255, 255, 0.4) inset,
-              1px 0 1px rgba(255, 255, 255, 0.4) inset,
-              -1px 0 1px rgba(255, 255, 255, 0.4) inset,
-              0 1px 1.5px rgba(0, 0, 0, 0.4);
   cursor: pointer;
 }
 
 html[dir=rtl] .tab {
   box-shadow: 0 1px 0 #FFFFFF inset,
               0 -1px 1px rgba(255, 255, 255, 0.4) inset,
               -1px 0 1px rgba(255, 255, 255, 0.4) inset,
               1px 0 1px rgba(255, 255, 255, 0.4) inset,
@@ -188,22 +184,16 @@ html[dir=rtl] .stack-trayed .tab-title {
 
 .front .focus {
   box-shadow: none !important;
 }
 
 /* Tab GroupItem
 ----------------------------------*/
 
-.tabInGroupItem {
-  border: none;
-  box-shadow: none !important;
-  margin: 4px;
-}
-
 .groupItem {
   cursor: move;
   border: 1px solid rgba(230,230,230,1);
   background-color: window;
   background-image: -moz-linear-gradient(rgba(255,255,255,.3),rgba(255,255,255,.1));
   border-radius: 0.4em;
   box-shadow:
     inset rgba(255, 255, 255, 0.6) 0 0 0 2px,
diff --git a/browser/themes/pinstripe/browser/browser.css b/browser/themes/pinstripe/browser/browser.css
--- a/browser/themes/pinstripe/browser/browser.css
+++ b/browser/themes/pinstripe/browser/browser.css
@@ -133,16 +133,20 @@ toolbarbutton.chevron {
   margin: 1px 0 0;
   padding: 0;
 }
 
 toolbarbutton.chevron > .toolbarbutton-text {
   display: none;
 }
 
+toolbar[mode="text"] toolbarbutton.chevron > .toolbarbutton-icon {
+  display: -moz-box; /* display chevron icon in text mode */
+}
+
 toolbarbutton.chevron:-moz-locale-dir(rtl) > .toolbarbutton-icon {
   -moz-transform: scaleX(-1);
 }
 
 /* ----- BOOKMARK BUTTONS ----- */
 
 toolbarbutton.bookmark-item {
   font-weight: bold;
diff --git a/browser/themes/pinstripe/browser/tabview/tabview.css b/browser/themes/pinstripe/browser/tabview/tabview.css
--- a/browser/themes/pinstripe/browser/tabview/tabview.css
+++ b/browser/themes/pinstripe/browser/tabview/tabview.css
@@ -12,24 +12,23 @@ body {
 #bg:-moz-window-inactive {
   background: -moz-linear-gradient(rgb(237,237,237),rgb(216,216,216));
 }
 
 /* Tabs
 ----------------------------------*/
 
 .tab {
+  margin: 8px;
   padding-top: 4px;
   -moz-padding-end: 6px;
   padding-bottom: 6px;
   -moz-padding-start: 4px;
-  background-color: #D7D7D7;
+  background-color: rgb(240,240,240);
   border-radius: 0.4em;
-  box-shadow: 0 1px 1.5px rgba(0, 0, 0, 0.4);
-  border: 1px solid rgba(255, 255, 255, 0.5);
   cursor: pointer;
 }
 
 .tab canvas,
 .cached-thumb {
   border: 1px solid rgba(0, 0, 0, 0.3);
 }
 
@@ -38,17 +37,17 @@ body {
   background-color: white;  
 }
 
 html[dir=rtl] .thumb {
   box-shadow: -1px 2px 0 rgba(0, 0, 0, 0.2);
 }
 
 .favicon {
-  background-color: #D7D7D7;
+  background-color: rgb(240,240,240);
   box-shadow:
     0 -1px 0 rgba(225, 225, 225, 0.8) inset,
     -1px 0 0 rgba(225, 225, 225, 0.8) inset;
   padding-top: 4px;
   -moz-padding-end: 6px;
   padding-bottom: 6px;
   -moz-padding-start: 4px;
   top: 4px;
@@ -186,27 +185,16 @@ html[dir=rtl] .stack-trayed .tab-title {
 .front.focus {
   box-shadow: none !important;
   border: none !important;
 }
 
 /* Tab GroupItem
 ----------------------------------*/
 
-.tabInGroupItem {
-  box-shadow: none;
-  border-color: transparent;
-  background-color: rgb(240,240,240);
-  margin: 8px;
-}
-
-.tabInGroupItem .favicon {
-  background-color: rgb(240,240,240);
-}
-
 .groupItem {
   cursor: move;
   background-color: rgb(240,240,240);
   border-radius: 0.4em;
   box-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
   border: 1px solid rgba(255, 255, 255, 0.5);
 }
 
diff --git a/browser/themes/winstripe/browser/tabview/tabview.css b/browser/themes/winstripe/browser/tabview/tabview.css
--- a/browser/themes/winstripe/browser/tabview/tabview.css
+++ b/browser/themes/winstripe/browser/tabview/tabview.css
@@ -8,28 +8,23 @@ body {
   background: url("chrome://browser/skin/tabview/grain.png") repeat scroll center top,
               -moz-linear-gradient(center top , #CCD9EA, #C7D5E7) repeat scroll 0 0 transparent;
 }
 
 /* Tabs
 ----------------------------------*/
 
 .tab {
+  margin: 4px;
   padding-top: 4px;
   -moz-padding-end: 6px;
   padding-bottom: 6px;
   -moz-padding-start: 4px;
   background-color: #E0EAF5;
   border-radius: 0.4em;
-  box-shadow:
-    0 1px 0 #FFFFFF inset,
-    0 -1px 1px rgba(255, 255, 255, 0.8) inset,
-    1px 0 1px rgba(255, 255, 255, 0.8) inset,
-    -1px 0 1px rgba(255, 255, 255, 0.8) inset,
-    0 1px 1.5px rgba(4, 38, 60, 0.4);
   cursor: pointer;
 }
 
 html[dir=rtl] .tab {
   box-shadow:
     0 1px 0 #FFFFFF inset,
     0 -1px 1px rgba(255, 255, 255, 0.8) inset,
     -1px 0 1px rgba(255, 255, 255, 0.8) inset,
@@ -203,26 +198,16 @@ html[dir=rtl] .tab.focus {
 
 .front.focus {
   box-shadow: none !important;
 }
 
 /* Tab GroupItem
 ----------------------------------*/
 
-.tabInGroupItem {
-  box-shadow: none;
-  background-color: #E0EAF5;
-  margin: 4px;
-}
-
-.tabInGroupItem .favicon {
-  background-color: #E0EAF5;
-}
-
 .groupItem {
   cursor: move;
   background-color: #E0EAF5;
   border-radius: 0.4em;
   box-shadow:
     0 1px 0 #FFFFFF inset,
     0 -1px 1px rgba(255, 255, 255, 0.8) inset,
     1px 0 1px rgba(255, 255, 255, 0.8) inset,
diff --git a/content/base/src/nsWebSocket.cpp b/content/base/src/nsWebSocket.cpp
--- a/content/base/src/nsWebSocket.cpp
+++ b/content/base/src/nsWebSocket.cpp
@@ -67,17 +67,18 @@
 #include "nsLayoutStatics.h"
 #include "nsIDOMCloseEvent.h"
 #include "nsICryptoHash.h"
 #include "jsdbgapi.h"
 #include "nsIJSContextStack.h"
 #include "nsJSUtils.h"
 #include "nsIScriptError.h"
 #include "nsNetUtil.h"
-#include "nsIWebSocketProtocol.h"
+#include "nsIWebSocketChannel.h"
+#include "nsIWebSocketListener.h"
 #include "nsILoadGroup.h"
 #include "nsIRequest.h"
 #include "mozilla/Preferences.h"
 
 using namespace mozilla;
 
 ////////////////////////////////////////////////////////////////////////////////
 // nsWebSocketEstablishedConnection
@@ -142,17 +143,17 @@ private:
                                const PRUnichar **aFormatStrings,
                                PRUint32          aFormatStringsLen);
   nsresult UpdateMustKeepAlive();
   
   // Frames that have been sent to websockethandler but not placed on wire
   PRUint32 mOutgoingBufferedAmount;
 
   nsWebSocket* mOwner; // weak reference
-  nsCOMPtr<nsIWebSocketProtocol> mWebSocketProtocol;
+  nsCOMPtr<nsIWebSocketChannel> mWebSocketChannel;
 
   PRPackedBool mClosedCleanly;
 
   enum ConnectionStatus {
     CONN_NOT_CONNECTED,
     CONN_CONNECTED_AND_READY,
     CONN_CLOSED
   };
@@ -182,17 +183,17 @@ nsWebSocketEstablishedConnection::nsWebS
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
   nsLayoutStatics::AddRef();
 }
 
 nsWebSocketEstablishedConnection::~nsWebSocketEstablishedConnection()
 {
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
   NS_ABORT_IF_FALSE(!mOwner, "Disconnect wasn't called!");
-  NS_ABORT_IF_FALSE(!mWebSocketProtocol, "Disconnect wasn't called!");
+  NS_ABORT_IF_FALSE(!mWebSocketChannel, "Disconnect wasn't called!");
 }
 
 nsresult
 nsWebSocketEstablishedConnection::PostMessage(const nsString& aMessage)
 {
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
 
   if (!mOwner) {
@@ -246,17 +247,17 @@ nsWebSocketEstablishedConnection::PostMe
 
   if (mStatus == CONN_CLOSED) {
     NS_ABORT_IF_FALSE(mOwner, "Posting data after disconnecting the websocket");
     // the tcp connection has been closed, but the main thread hasn't received
     // the event for disconnecting the object yet.
     rv = NS_BASE_STREAM_CLOSED;
   } else {
     mOutgoingBufferedAmount += buf.Length();
-    mWebSocketProtocol->SendMsg(buf);
+    mWebSocketChannel->SendMsg(buf);
     rv = NS_OK;
   }
 
   UpdateMustKeepAlive();
   ENSURE_SUCCESS_AND_FAIL_IF_FAILED(rv, rv);
 
   return NS_OK;
 }
@@ -266,46 +267,46 @@ nsWebSocketEstablishedConnection::Init(n
 {
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
   NS_ABORT_IF_FALSE(!mOwner, "WebSocket's connection is already initialized");
 
   nsresult rv;
   mOwner = aOwner;
 
   if (mOwner->mSecure) {
-    mWebSocketProtocol =
+    mWebSocketChannel =
       do_CreateInstance("@mozilla.org/network/protocol;1?name=wss", &rv);
   }
   else {
-    mWebSocketProtocol =
+    mWebSocketChannel =
       do_CreateInstance("@mozilla.org/network/protocol;1?name=ws", &rv);
   }
   NS_ENSURE_SUCCESS(rv, rv);
   
-  rv = mWebSocketProtocol->SetNotificationCallbacks(this);
+  rv = mWebSocketChannel->SetNotificationCallbacks(this);
   NS_ENSURE_SUCCESS(rv, rv);
 
   // add ourselves to the document's load group and
   // provide the http stack the loadgroup info too
   nsCOMPtr<nsILoadGroup> loadGroup;
   rv = GetLoadGroup(getter_AddRefs(loadGroup));
   if (loadGroup) {
-    rv = mWebSocketProtocol->SetLoadGroup(loadGroup);
+    rv = mWebSocketChannel->SetLoadGroup(loadGroup);
     NS_ENSURE_SUCCESS(rv, rv);
     rv = loadGroup->AddRequest(this, nsnull);
     NS_ENSURE_SUCCESS(rv, rv);
   }
 
   if (!mOwner->mProtocol.IsEmpty())
-    rv = mWebSocketProtocol->SetProtocol(mOwner->mProtocol);
+    rv = mWebSocketChannel->SetProtocol(mOwner->mProtocol);
   NS_ENSURE_SUCCESS(rv, rv);
 
   nsCString utf8Origin;
   CopyUTF16toUTF8(mOwner->mUTF16Origin, utf8Origin);
-  rv = mWebSocketProtocol->AsyncOpen(mOwner->mURI,
+  rv = mWebSocketChannel->AsyncOpen(mOwner->mURI,
                                      utf8Origin, this, nsnull);
   NS_ENSURE_SUCCESS(rv, rv);
 
   return NS_OK;
 }
 
 nsresult
 nsWebSocketEstablishedConnection::PrintErrorOnConsole(const char *aBundleURI,
@@ -383,17 +384,17 @@ nsWebSocketEstablishedConnection::Close(
   mOwner->SetReadyState(nsIWebSocket::CLOSING);
 
   if (mStatus == CONN_CLOSED) {
     mOwner->SetReadyState(nsIWebSocket::CLOSED);
     Disconnect();
     return NS_OK;
   }
 
-  return mWebSocketProtocol->Close();
+  return mWebSocketChannel->Close();
 }
 
 nsresult
 nsWebSocketEstablishedConnection::ConsoleError()
 {
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
   nsresult rv;
   if (!mOwner) return NS_OK;
@@ -446,17 +447,17 @@ nsWebSocketEstablishedConnection::Discon
 
   // If mOwner is deleted when calling mOwner->DontKeepAliveAnyMore()
   // then this method can be called again, and we will get a deadlock.
   nsRefPtr<nsWebSocket> kungfuDeathGrip = mOwner;
   
   mOwner->DontKeepAliveAnyMore();
   mStatus = CONN_CLOSED;
   mOwner = nsnull;
-  mWebSocketProtocol = nsnull;
+  mWebSocketChannel = nsnull;
 
   nsLayoutStatics::Release();
   return NS_OK;
 }
 
 nsresult
 nsWebSocketEstablishedConnection::UpdateMustKeepAlive()
 {
@@ -499,17 +500,17 @@ nsWebSocketEstablishedConnection::OnBina
 NS_IMETHODIMP
 nsWebSocketEstablishedConnection::OnStart(nsISupports *aContext)
 {
   NS_ABORT_IF_FALSE(NS_IsMainThread(), "Not running on main thread");
   if (!mOwner)
     return NS_OK;
 
   if (!mOwner->mProtocol.IsEmpty())
-    mWebSocketProtocol->GetProtocol(mOwner->mProtocol);
+    mWebSocketChannel->GetProtocol(mOwner->mProtocol);
 
   mStatus = CONN_CONNECTED_AND_READY;
   mOwner->SetReadyState(nsIWebSocket::OPEN);
   return NS_OK;
 }
 
 NS_IMETHODIMP
 nsWebSocketEstablishedConnection::OnStop(nsISupports *aContext,
diff --git a/content/base/test/Makefile.in b/content/base/test/Makefile.in
--- a/content/base/test/Makefile.in
+++ b/content/base/test/Makefile.in
@@ -412,18 +412,18 @@ include $(topsrcdir)/config/rules.mk
 		file_bug562137.txt \
 		test_bug548193.html \
 		file_bug548193.sjs \
 		test_html_colors_quirks.html \
 		test_html_colors_standards.html \
 		test_bug300992.html \
 		test_websocket_hello.html \
 		file_websocket_hello_wsh.py \
-		test_ws_basic_tests.html \
-		file_ws_basic_tests_wsh.py \
+		test_websocket_basic.html \
+		file_websocket_basic_wsh.py \
 		test_websocket.html \
 		file_websocket_wsh.py \
 		file_websocket_http_resource.txt \
 		test_x-frame-options.html \
 		file_x-frame-options_main.html \
 		file_x-frame-options_page.sjs \
 		test_createHTMLDocument.html \
 		test_bug622088.html \
diff --git a/content/base/test/file_ws_basic_tests_wsh.py b/content/base/test/file_websocket_basic_wsh.py
rename from content/base/test/file_ws_basic_tests_wsh.py
rename to content/base/test/file_websocket_basic_wsh.py
diff --git a/content/base/test/test_ws_basic_tests.html b/content/base/test/test_websocket_basic.html
rename from content/base/test/test_ws_basic_tests.html
rename to content/base/test/test_websocket_basic.html
--- a/content/base/test/test_ws_basic_tests.html
+++ b/content/base/test/test_websocket_basic.html
@@ -14,30 +14,30 @@
 <div id="content" style="display: none">
 </div>
 <pre id="test">
 <script class="testbody" type="text/javascript">
 
 var ws;
 
 var params = ["protocol", "resource", "origin", "end"];
-var results = ["test", "/tests/content/base/test/file_ws_basic_tests", "http://mochi.test:8888", "end"];
+var results = ["test", "/tests/content/base/test/file_websocket_basic", "http://mochi.test:8888", "end"];
 
 function forcegc(){
   SpecialPowers.forceGC();
   SpecialPowers.gc();
 }
 
 function finishWSTest() {
     SimpleTest.finish();
 }
 
 function testWebSocket () {
-  var url = "ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests";
-  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests", "test");
+  var url = "ws://mochi.test:8888/tests/content/base/test/file_websocket_basic";
+  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_websocket_basic", "test");
   is(ws.url, url, "Wrong Websocket.url!");
   ws.onopen = function(e) {
     for (var i = 0; i < params.length; ++i) {
       document.getElementById('log').textContent += "sending " + params[i] + "\n";
       ws.send(params[i]);
     }
   }
   ws.onclose = function(e) {
@@ -52,17 +52,17 @@ function testWebSocket () {
   ws.onmessage = function(e) {
     document.getElementById('log').textContent += "\n" + e.data;
     is(e.data, results[0], "Unexpected message");
     results.shift();
   }
 }
 
 function testWebSocket2() {
-  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests", "test");
+  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_websocket_basic", "test");
   var testCount = 1000; // Send lots of messages
   var messageCount = 0;
   var testMessage = "test message";
   ws.onopen = function(e) {
     for (var i = 0; i < testCount; ++i) {
       ws.send(testMessage + (i + 1));
     }
     ws.send("end");
@@ -82,17 +82,17 @@ function testWebSocket2() {
     document.getElementById('log').textContent = messageCount;
     if (messageCount == testCount) {
       this.onmessage = null;
     }
   }
 }
 
 function testWebSocket3() {
-  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests", "test");
+  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_websocket_basic", "test");
   var testCount = 100; // Send lots of messages
   var messageCount = 0;
   var testMessage = "test message";
   ws.onopen = function(e) {
     for (var i = 0; i < testCount; ++i) {
       forcegc(); // Do something evil, call cycle collector a lot.
       ws.send(testMessage + (i + 1));
     }
@@ -114,17 +114,17 @@ function testWebSocket3() {
     document.getElementById('log').textContent = messageCount;
     if (messageCount == testCount) {
       this.onmessage = null;
     }
   }
 }
 
 function testWebSocket4() {
-  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests", "test");
+  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_websocket_basic", "test");
   // String length = (10,000 - 1) * 23 = 229,977 = almost 225 KiB.
   var longString = new Array(10000).join("-huge websocket message");
   ws.onopen = function(e) {
     is(this, ws, "'this' should point to the WebSocket. (1)");
     ws.send(longString);
   }
   ws.onclose = function(e) {
     is(this, ws, "'this' should point to the WebSocket. (2)");
@@ -141,17 +141,17 @@ function testWebSocket4() {
     is(e.data.length, longString.length, "Length of received message");
     ok(e.data == longString, "Content of received message");
     document.getElementById('log').textContent += "\nReceived the huge message";
     this.close();
   }
 }
 
 function testWebSocket5() {
-  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_ws_basic_tests", "test");
+  ws = new WebSocket("ws://mochi.test:8888/tests/content/base/test/file_websocket_basic", "test");
   ws.onopen = function(e) {
     this.close();
   }
   ws.onclose = function(e) {
     ok(e.wasClean, "Connection closed cleanly");
     is(this.bufferedAmount, 0, "Shouldn't have anything buffered");
     var msg = "some data";
     this.send(msg);
diff --git a/content/media/nsBuiltinDecoderReader.h b/content/media/nsBuiltinDecoderReader.h
--- a/content/media/nsBuiltinDecoderReader.h
+++ b/content/media/nsBuiltinDecoderReader.h
@@ -263,23 +263,23 @@ public:
   }
 
   VideoData(PRInt64 aOffset,
             PRInt64 aTime,
             PRInt64 aEndTime,
             PRBool aKeyframe,
             PRInt64 aTimecode,
             nsIntSize aDisplay)
-    : mOffset(aOffset),
+    : mDisplay(aDisplay),
+      mOffset(aOffset),
       mTime(aTime),
       mEndTime(aEndTime),
       mTimecode(aTimecode),
       mDuplicate(PR_FALSE),
-      mKeyframe(aKeyframe),
-      mDisplay(aDisplay)
+      mKeyframe(aKeyframe)
   {
     MOZ_COUNT_CTOR(VideoData);
     NS_ASSERTION(aEndTime >= aTime, "Frame must start before it ends.");
   }
 
 };
 
 // Thread and type safe wrapper around nsDeque.
diff --git a/content/svg/content/src/nsSVGIntegerPair.cpp b/content/svg/content/src/nsSVGIntegerPair.cpp
--- a/content/svg/content/src/nsSVGIntegerPair.cpp
+++ b/content/svg/content/src/nsSVGIntegerPair.cpp
@@ -40,24 +40,24 @@
 #include "prdtoa.h"
 #ifdef MOZ_SMIL
 #include "nsSMILValue.h"
 #include "SVGIntegerPairSMILType.h"
 #endif // MOZ_SMIL
 
 using namespace mozilla;
 
-NS_SVG_VAL_IMPL_CYCLE_COLLECTION(nsSVGIntegerPair::DOMAnimatedIntegerPair, mSVGElement)
+NS_SVG_VAL_IMPL_CYCLE_COLLECTION(nsSVGIntegerPair::DOMAnimatedInteger, mSVGElement)
 
-NS_IMPL_CYCLE_COLLECTING_ADDREF(nsSVGIntegerPair::DOMAnimatedIntegerPair)
-NS_IMPL_CYCLE_COLLECTING_RELEASE(nsSVGIntegerPair::DOMAnimatedIntegerPair)
+NS_IMPL_CYCLE_COLLECTING_ADDREF(nsSVGIntegerPair::DOMAnimatedInteger)
+NS_IMPL_CYCLE_COLLECTING_RELEASE(nsSVGIntegerPair::DOMAnimatedInteger)
 
-DOMCI_DATA(SVGAnimatedIntegerPair, nsSVGIntegerPair::DOMAnimatedIntegerPair)
+DOMCI_DATA(SVGAnimatedIntegerPair, nsSVGIntegerPair::DOMAnimatedInteger)
 
-NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(nsSVGIntegerPair::DOMAnimatedIntegerPair)
+NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(nsSVGIntegerPair::DOMAnimatedInteger)
   NS_INTERFACE_MAP_ENTRY(nsIDOMSVGAnimatedInteger)
   NS_INTERFACE_MAP_ENTRY(nsISupports)
   NS_DOM_INTERFACE_MAP_ENTRY_CLASSINFO(SVGAnimatedInteger)
 NS_INTERFACE_MAP_END
 
 /* Implementation */
 
 static nsresult
@@ -191,17 +191,17 @@ nsSVGIntegerPair::SetAnimValue(const PRI
   aSVGElement->DidAnimateIntegerPair(mAttrEnum);
 }
 
 nsresult
 nsSVGIntegerPair::ToDOMAnimatedInteger(nsIDOMSVGAnimatedInteger **aResult,
                                        PairIndex aIndex,
                                        nsSVGElement *aSVGElement)
 {
-  *aResult = new DOMAnimatedIntegerPair(this, aIndex, aSVGElement);
+  *aResult = new DOMAnimatedInteger(this, aIndex, aSVGElement);
   NS_ADDREF(*aResult);
   return NS_OK;
 }
 
 #ifdef MOZ_SMIL
 nsISMILAttr*
 nsSVGIntegerPair::ToSMILAttr(nsSVGElement *aSVGElement)
 {
diff --git a/content/svg/content/src/nsSVGIntegerPair.h b/content/svg/content/src/nsSVGIntegerPair.h
--- a/content/svg/content/src/nsSVGIntegerPair.h
+++ b/content/svg/content/src/nsSVGIntegerPair.h
@@ -97,22 +97,22 @@ private:
 
   PRInt32 mAnimVal[2];
   PRInt32 mBaseVal[2];
   PRUint8 mAttrEnum; // element specified tracking for attribute
   PRPackedBool mIsAnimated;
   PRPackedBool mIsBaseSet;
 
 public:
-  struct DOMAnimatedIntegerPair : public nsIDOMSVGAnimatedInteger
+  struct DOMAnimatedInteger : public nsIDOMSVGAnimatedInteger
   {
     NS_DECL_CYCLE_COLLECTING_ISUPPORTS
-    NS_DECL_CYCLE_COLLECTION_CLASS(DOMAnimatedIntegerPair)
+    NS_DECL_CYCLE_COLLECTION_CLASS(DOMAnimatedInteger)
 
-    DOMAnimatedIntegerPair(nsSVGIntegerPair* aVal, PairIndex aIndex, nsSVGElement *aSVGElement)
+    DOMAnimatedInteger(nsSVGIntegerPair* aVal, PairIndex aIndex, nsSVGElement *aSVGElement)
       : mVal(aVal), mSVGElement(aSVGElement), mIndex(aIndex) {}
 
     nsSVGIntegerPair* mVal; // kept alive because it belongs to content
     nsRefPtr<nsSVGElement> mSVGElement;
     PairIndex mIndex; // are we the first or second integer
 
     NS_IMETHOD GetBaseVal(PRInt32* aResult)
       { *aResult = mVal->GetBaseValue(mIndex); return NS_OK; }
diff --git a/content/svg/content/src/nsSVGNumberPair.cpp b/content/svg/content/src/nsSVGNumberPair.cpp
--- a/content/svg/content/src/nsSVGNumberPair.cpp
+++ b/content/svg/content/src/nsSVGNumberPair.cpp
@@ -40,24 +40,24 @@
 #include "prdtoa.h"
 #ifdef MOZ_SMIL
 #include "nsSMILValue.h"
 #include "SVGNumberPairSMILType.h"
 #endif // MOZ_SMIL
 
 using namespace mozilla;
 
-NS_SVG_VAL_IMPL_CYCLE_COLLECTION(nsSVGNumberPair::DOMAnimatedNumberPair, mSVGElement)
+NS_SVG_VAL_IMPL_CYCLE_COLLECTION(nsSVGNumberPair::DOMAnimatedNumber, mSVGElement)
 
-NS_IMPL_CYCLE_COLLECTING_ADDREF(nsSVGNumberPair::DOMAnimatedNumberPair)
-NS_IMPL_CYCLE_COLLECTING_RELEASE(nsSVGNumberPair::DOMAnimatedNumberPair)
+NS_IMPL_CYCLE_COLLECTING_ADDREF(nsSVGNumberPair::DOMAnimatedNumber)
+NS_IMPL_CYCLE_COLLECTING_RELEASE(nsSVGNumberPair::DOMAnimatedNumber)
 
-DOMCI_DATA(SVGAnimatedNumberPair, nsSVGNumberPair::DOMAnimatedNumberPair)
+DOMCI_DATA(SVGAnimatedNumberPair, nsSVGNumberPair::DOMAnimatedNumber)
 
-NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(nsSVGNumberPair::DOMAnimatedNumberPair)
+NS_INTERFACE_MAP_BEGIN_CYCLE_COLLECTION(nsSVGNumberPair::DOMAnimatedNumber)
   NS_INTERFACE_MAP_ENTRY(nsIDOMSVGAnimatedNumber)
   NS_INTERFACE_MAP_ENTRY(nsISupports)
   NS_DOM_INTERFACE_MAP_ENTRY_CLASSINFO(SVGAnimatedNumber)
 NS_INTERFACE_MAP_END
 
 /* Implementation */
 
 static nsresult
@@ -190,17 +190,17 @@ nsSVGNumberPair::SetAnimValue(const floa
   aSVGElement->DidAnimateNumberPair(mAttrEnum);
 }
 
 nsresult
 nsSVGNumberPair::ToDOMAnimatedNumber(nsIDOMSVGAnimatedNumber **aResult,
                                      PairIndex aIndex,
                                      nsSVGElement *aSVGElement)
 {
-  *aResult = new DOMAnimatedNumberPair(this, aIndex, aSVGElement);
+  *aResult = new DOMAnimatedNumber(this, aIndex, aSVGElement);
   NS_ADDREF(*aResult);
   return NS_OK;
 }
 
 #ifdef MOZ_SMIL
 nsISMILAttr*
 nsSVGNumberPair::ToSMILAttr(nsSVGElement *aSVGElement)
 {
diff --git a/content/svg/content/src/nsSVGNumberPair.h b/content/svg/content/src/nsSVGNumberPair.h
--- a/content/svg/content/src/nsSVGNumberPair.h
+++ b/content/svg/content/src/nsSVGNumberPair.h
@@ -98,22 +98,22 @@ private:
 
   float mAnimVal[2];
   float mBaseVal[2];
   PRUint8 mAttrEnum; // element specified tracking for attribute
   PRPackedBool mIsAnimated;
   PRPackedBool mIsBaseSet;
 
 public:
-  struct DOMAnimatedNumberPair : public nsIDOMSVGAnimatedNumber
+  struct DOMAnimatedNumber : public nsIDOMSVGAnimatedNumber
   {
     NS_DECL_CYCLE_COLLECTING_ISUPPORTS
-    NS_DECL_CYCLE_COLLECTION_CLASS(DOMAnimatedNumberPair)
+    NS_DECL_CYCLE_COLLECTION_CLASS(DOMAnimatedNumber)
 
-    DOMAnimatedNumberPair(nsSVGNumberPair* aVal, PairIndex aIndex, nsSVGElement *aSVGElement)
+    DOMAnimatedNumber(nsSVGNumberPair* aVal, PairIndex aIndex, nsSVGElement *aSVGElement)
       : mVal(aVal), mSVGElement(aSVGElement), mIndex(aIndex) {}
 
     nsSVGNumberPair* mVal; // kept alive because it belongs to content
     nsRefPtr<nsSVGElement> mSVGElement;
     PairIndex mIndex; // are we the first or second number
 
     NS_IMETHOD GetBaseVal(float* aResult)
       { *aResult = mVal->GetBaseValue(mIndex); return NS_OK; }
diff --git a/docshell/test/test_bug634834.html b/docshell/test/test_bug634834.html
--- a/docshell/test/test_bug634834.html
+++ b/docshell/test/test_bug634834.html
@@ -8,18 +8,16 @@ https://bugzilla.mozilla.org/show_bug.cg
   <script type="application/javascript" src="/MochiKit/packed.js"></script>
   <script type="application/javascript" src="/tests/SimpleTest/SimpleTest.js"></script>
   <script type="application/javascript" src="/tests/SimpleTest/EventUtils.js"></script>
   <link rel="stylesheet" type="text/css" href="/tests/SimpleTest/test.css"/>
 </head>
 <body>
 <a target="_blank" href="https://bugzilla.mozilla.org/show_bug.cgi?id=634834">Mozilla Bug 634834</a>
 
-<iframe id='iframe' src='file_bug634834.html' onload='iframe_loaded()'></iframe>
-
 <script type='application/javascript;version=1.7'>
 SimpleTest.waitForExplicitFinish();
 
 function iframe_loaded() {
   var loadedAfterPushstate = false;
   $('iframe').onload = function() {
     loadedAfterPushstate = true;
   }
@@ -44,10 +42,13 @@ function iframe_loaded() {
   }
   catch(e) {
     ok(true, 'pushState threw an exception.');
   }
   SimpleTest.finish();
 }
 
 </script>
+
+<iframe id='iframe' src='file_bug634834.html' onload='iframe_loaded()'></iframe>
+
 </body>
 </html>
diff --git a/dom/base/nsDOMClassInfo.cpp b/dom/base/nsDOMClassInfo.cpp
--- a/dom/base/nsDOMClassInfo.cpp
+++ b/dom/base/nsDOMClassInfo.cpp
@@ -1157,26 +1157,22 @@ static nsDOMClassInfoData sClassInfoData
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedAngle, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedBoolean, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedEnumeration, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedInteger, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
-  NS_DEFINE_CLASSINFO_DATA(SVGAnimatedIntegerPair, nsDOMGenericSH,
-                           DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedLength, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedLengthList, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedNumber, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)    
-  NS_DEFINE_CLASSINFO_DATA(SVGAnimatedNumberPair, nsDOMGenericSH,
-                           DOM_DEFAULT_SCRIPTABLE_FLAGS)    
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedNumberList, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)    
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedPreserveAspectRatio, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedRect, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
   NS_DEFINE_CLASSINFO_DATA(SVGAnimatedString, nsDOMGenericSH,
                            DOM_DEFAULT_SCRIPTABLE_FLAGS)
@@ -3674,36 +3670,28 @@ nsDOMClassInfo::Init()
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedEnumeration, nsIDOMSVGAnimatedEnumeration)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedEnumeration)
   DOM_CLASSINFO_MAP_END
 
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedInteger, nsIDOMSVGAnimatedInteger)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedInteger)
   DOM_CLASSINFO_MAP_END
 
-  DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedIntegerPair, nsIDOMSVGAnimatedInteger)
-    DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedInteger)
-  DOM_CLASSINFO_MAP_END
-
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedLength, nsIDOMSVGAnimatedLength)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedLength)
   DOM_CLASSINFO_MAP_END
 
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedLengthList, nsIDOMSVGAnimatedLengthList)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedLengthList)
   DOM_CLASSINFO_MAP_END
 
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedNumber, nsIDOMSVGAnimatedNumber)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedNumber)
   DOM_CLASSINFO_MAP_END
 
-  DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedNumberPair, nsIDOMSVGAnimatedNumber)
-    DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedNumber)
-  DOM_CLASSINFO_MAP_END
-
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedNumberList, nsIDOMSVGAnimatedNumberList)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedNumberList)
   DOM_CLASSINFO_MAP_END
 
   DOM_CLASSINFO_MAP_BEGIN(SVGAnimatedPreserveAspectRatio, nsIDOMSVGAnimatedPreserveAspectRatio)
     DOM_CLASSINFO_MAP_ENTRY(nsIDOMSVGAnimatedPreserveAspectRatio)
   DOM_CLASSINFO_MAP_END
 
diff --git a/dom/base/nsDOMClassInfoClasses.h b/dom/base/nsDOMClassInfoClasses.h
--- a/dom/base/nsDOMClassInfoClasses.h
+++ b/dom/base/nsDOMClassInfoClasses.h
@@ -300,21 +300,19 @@ DOMCI_CLASS(SVGTSpanElement)
 DOMCI_CLASS(SVGUseElement)
 
 // other SVG classes
 DOMCI_CLASS(SVGAngle)
 DOMCI_CLASS(SVGAnimatedAngle)
 DOMCI_CLASS(SVGAnimatedBoolean)
 DOMCI_CLASS(SVGAnimatedEnumeration)
 DOMCI_CLASS(SVGAnimatedInteger)
-DOMCI_CLASS(SVGAnimatedIntegerPair)
 DOMCI_CLASS(SVGAnimatedLength)
 DOMCI_CLASS(SVGAnimatedLengthList)
 DOMCI_CLASS(SVGAnimatedNumber)
-DOMCI_CLASS(SVGAnimatedNumberPair)
 DOMCI_CLASS(SVGAnimatedNumberList)
 DOMCI_CLASS(SVGAnimatedPreserveAspectRatio)
 DOMCI_CLASS(SVGAnimatedRect)
 DOMCI_CLASS(SVGAnimatedString)
 DOMCI_CLASS(SVGAnimatedTransformList)
 DOMCI_CLASS(SVGEvent)
 DOMCI_CLASS(SVGException)
 DOMCI_CLASS(SVGLength)
diff --git a/gfx/layers/ImageLayers.h b/gfx/layers/ImageLayers.h
--- a/gfx/layers/ImageLayers.h
+++ b/gfx/layers/ImageLayers.h
@@ -40,16 +40,17 @@
 
 #include "Layers.h"
 
 #include "gfxPattern.h"
 #include "nsThreadUtils.h"
 #include "nsCoreAnimationSupport.h"
 #include "mozilla/ReentrantMonitor.h"
 #include "mozilla/TimeStamp.h"
+#include "mozilla/mozalloc.h"
 
 namespace mozilla {
 namespace layers {
 
 enum StereoMode {
   STEREO_MODE_MONO,
   STEREO_MODE_LEFT_RIGHT,
   STEREO_MODE_RIGHT_LEFT,
@@ -402,16 +403,22 @@ public:
     PRUint8* mCrChannel;
     PRInt32 mCbCrStride;
     gfxIntSize mCbCrSize;
     // Picture region
     PRUint32 mPicX;
     PRUint32 mPicY;
     gfxIntSize mPicSize;
     StereoMode mStereoMode;
+
+    nsIntRect GetPictureRect() const {
+      return nsIntRect(mPicX, mPicY,
+                       mPicSize.width,
+                       mPicSize.height);
+    }
   };
 
   enum {
     MAX_DIMENSION = 16384
   };
 
   /**
    * This makes a copy of the data buffers.
@@ -428,16 +435,30 @@ public:
    */
   virtual void SetDelayedConversion(PRBool aDelayed) { }
 
   /**
    * Grab the original YUV data. This is optional.
    */
   virtual const Data* GetData() { return nsnull; }
 
+  /**
+   * Make a copy of the YCbCr data.
+   *
+   * @param aDest           Data object to store the plane data in.
+   * @param aDestSize       Size of the Y plane that was copied.
+   * @param aDestBufferSize Number of bytes allocated for storage.
+   * @param aData           Input image data.
+   * @return                Raw data pointer for the planes or nsnull on failure.
+   */
+  PRUint8 *CopyData(Data& aDest, gfxIntSize& aDestSize,
+                    PRUint32& aDestBufferSize, const Data& aData);
+
+  virtual PRUint8* AllocateBuffer(PRUint32 aSize);
+
 protected:
   PlanarYCbCrImage(void* aImplData) : Image(aImplData, PLANAR_YCBCR) {}
 };
 
 /**
  * Currently, the data in a CairoImage surface is treated as being in the
  * device output color space.
  */
diff --git a/gfx/layers/Layers.cpp b/gfx/layers/Layers.cpp
--- a/gfx/layers/Layers.cpp
+++ b/gfx/layers/Layers.cpp
@@ -476,16 +476,66 @@ ContainerLayer::DidRemoveChild(Layer* aL
 void
 ContainerLayer::DidInsertChild(Layer* aLayer)
 {
   if (aLayer->GetType() == TYPE_READBACK) {
     mMayHaveReadbackChild = PR_TRUE;
   }
 }
 
+PRUint8* 
+PlanarYCbCrImage::AllocateBuffer(PRUint32 aSize)
+{
+  const fallible_t fallible = fallible_t();
+  return new (fallible) PRUint8[aSize]; 
+}
+
+PRUint8*
+PlanarYCbCrImage::CopyData(Data& aDest, gfxIntSize& aDestSize,
+                           PRUint32& aDestBufferSize, const Data& aData)
+{
+  aDest = aData;
+
+  /* We always have a multiple of 16 width so we can force the stride */
+  aDest.mYStride = aDest.mYSize.width;
+  aDest.mCbCrStride = aDest.mCbCrSize.width;
+
+  // update buffer size
+  aDestBufferSize = aDest.mCbCrStride * aDest.mCbCrSize.height * 2 +
+                    aDest.mYStride * aDest.mYSize.height;
+
+  // get new buffer
+  PRUint8* buffer = AllocateBuffer(aDestBufferSize); 
+  if (!buffer)
+    return nsnull;
+
+  aDest.mYChannel = buffer;
+  aDest.mCbChannel = aDest.mYChannel + aDest.mYStride * aDest.mYSize.height;
+  aDest.mCrChannel = aDest.mCbChannel + aDest.mCbCrStride * aDest.mCbCrSize.height;
+
+  for (int i = 0; i < aDest.mYSize.height; i++) {
+    memcpy(aDest.mYChannel + i * aDest.mYStride,
+           aData.mYChannel + i * aData.mYStride,
+           aDest.mYStride);
+  }
+  for (int i = 0; i < aDest.mCbCrSize.height; i++) {
+    memcpy(aDest.mCbChannel + i * aDest.mCbCrStride,
+           aData.mCbChannel + i * aData.mCbCrStride,
+           aDest.mCbCrStride);
+    memcpy(aDest.mCrChannel + i * aDest.mCbCrStride,
+           aData.mCrChannel + i * aData.mCbCrStride,
+           aDest.mCbCrStride);
+  }
+
+  aDestSize = aData.mPicSize;
+  return buffer;
+}
+                         
+
+
 #ifdef MOZ_LAYERS_HAVE_LOG
 
 static nsACString& PrintInfo(nsACString& aTo, ShadowLayer* aShadowLayer);
 
 void
 Layer::Dump(FILE* aFile, const char* aPrefix)
 {
   DumpSelf(aFile, aPrefix);
diff --git a/gfx/layers/basic/BasicImages.cpp b/gfx/layers/basic/BasicImages.cpp
--- a/gfx/layers/basic/BasicImages.cpp
+++ b/gfx/layers/basic/BasicImages.cpp
@@ -144,88 +144,26 @@ void
 BasicPlanarYCbCrImage::SetData(const Data& aData)
 {
   // Do some sanity checks to prevent integer overflow
   if (aData.mYSize.width > 16384 || aData.mYSize.height > 16384) {
     NS_ERROR("Illegal width or height");
     return;
   }
   
-  gfx::YUVType type = gfx::YV12;
-  int width_shift = 0;
-  int height_shift = 0;
-  if (aData.mYSize.width == aData.mCbCrSize.width &&
-      aData.mYSize.height == aData.mCbCrSize.height) {
-    type = gfx::YV24;
-    width_shift = 0;
-    height_shift = 0;
-  }
-  else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-           aData.mYSize.height == aData.mCbCrSize.height) {
-    type = gfx::YV16;
-    width_shift = 1;
-    height_shift = 0;
-  }
-  else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-           aData.mYSize.height / 2 == aData.mCbCrSize.height ) {
-    type = gfx::YV12;
-    width_shift = 1;
-    height_shift = 1;
-  }
-  else {
-    NS_ERROR("YCbCr format not supported");
-  }
-
   if (mDelayedConversion) {
-
-    mData = aData;
-    mData.mCbCrStride = mData.mCbCrSize.width = aData.mPicSize.width >> width_shift;
-    // Round up the values for width and height to make sure we sample enough data
-    // for the last pixel - See bug 590735
-    if (width_shift && (aData.mPicSize.width & 1)) {
-      mData.mCbCrStride++;
-      mData.mCbCrSize.width++;
-    }
-    mData.mCbCrSize.height = aData.mPicSize.height >> height_shift;
-    if (height_shift && (aData.mPicSize.height & 1)) {
-        mData.mCbCrSize.height++;
-    }
-    mData.mYSize = aData.mPicSize;
-    mData.mYStride = mData.mYSize.width;
-    mBufferSize = mData.mCbCrStride * mData.mCbCrSize.height * 2 +
-                  mData.mYStride * mData.mYSize.height;
-    mBuffer = new PRUint8[mBufferSize];
-    
-    mData.mYChannel = mBuffer;
-    mData.mCbChannel = mData.mYChannel + mData.mYStride * mData.mYSize.height;
-    mData.mCrChannel = mData.mCbChannel + mData.mCbCrStride * mData.mCbCrSize.height;
-    int cbcr_x = aData.mPicX >> width_shift;
-    int cbcr_y = aData.mPicY >> height_shift;
-
-    for (int i = 0; i < mData.mYSize.height; i++) {
-      memcpy(mData.mYChannel + i * mData.mYStride,
-             aData.mYChannel + ((aData.mPicY + i) * aData.mYStride) + aData.mPicX,
-             mData.mYStride);
-    }
-    for (int i = 0; i < mData.mCbCrSize.height; i++) {
-      memcpy(mData.mCbChannel + i * mData.mCbCrStride,
-             aData.mCbChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-             mData.mCbCrStride);
-    }
-    for (int i = 0; i < mData.mCbCrSize.height; i++) {
-      memcpy(mData.mCrChannel + i * mData.mCbCrStride,
-             aData.mCrChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-             mData.mCbCrStride);
-    }
-
-    // Fix picture rect to be correct
-    mData.mPicX = mData.mPicY = 0;
-    mSize = aData.mPicSize;
+    mBuffer = CopyData(mData, mSize, mBufferSize, aData);
     return;
   }
+  
+  gfx::YUVType type = 
+    gfx::TypeFromSize(aData.mYSize.width,
+                      aData.mYSize.height,
+                      aData.mCbCrSize.width,
+                      aData.mCbCrSize.height);
 
   gfxASurface::gfxImageFormat format = GetOffscreenFormat();
 
   // 'prescale' is true if the scaling is to be done as part of the
   // YCbCr to RGB conversion rather than on the RGB data when rendered.
   PRBool prescale = mScaleHint.width > 0 && mScaleHint.height > 0 &&
                     mScaleHint != aData.mPicSize;
   if (format == gfxASurface::ImageFormatRGB16_565) {
diff --git a/gfx/layers/basic/BasicLayers.cpp b/gfx/layers/basic/BasicLayers.cpp
--- a/gfx/layers/basic/BasicLayers.cpp
+++ b/gfx/layers/basic/BasicLayers.cpp
@@ -2218,37 +2218,43 @@ BasicShadowableImageLayer::Paint(gfxCont
       if (!BasicManager()->AllocDoubleBuffer(
             mCbCrSize,
             gfxASurface::CONTENT_ALPHA,
             getter_AddRefs(tmpVSurface), getter_AddRefs(mBackBufferV)))
         NS_RUNTIMEABORT("creating ImageLayer 'front buffer' failed!");
 
       YUVImage yuv(tmpYSurface->GetShmem(),
                    tmpUSurface->GetShmem(),
-                   tmpVSurface->GetShmem());
+                   tmpVSurface->GetShmem(),
+                   nsIntRect());
 
       BasicManager()->CreatedImageBuffer(BasicManager()->Hold(this),
                                          nsIntSize(mSize.width, mSize.height),
                                          yuv);
 
     }
       
-    memcpy(mBackBufferY->Data(), 
-           data->mYChannel, 
-           data->mYStride * mSize.height);
-    memcpy(mBackBufferU->Data(), 
-           data->mCbChannel, 
-           data->mCbCrStride * mCbCrSize.height);
-    memcpy(mBackBufferV->Data(), 
-           data->mCrChannel, 
-           data->mCbCrStride * mCbCrSize.height);
+    for (int i = 0; i < data->mYSize.height; i++) {
+      memcpy(mBackBufferY->Data() + i * mBackBufferY->Stride(),
+             data->mYChannel + i * data->mYStride,
+             data->mYSize.width);
+    }
+    for (int i = 0; i < data->mCbCrSize.height; i++) {
+      memcpy(mBackBufferU->Data() + i * mBackBufferU->Stride(),
+             data->mCbChannel + i * data->mCbCrStride,
+             data->mCbCrSize.width);
+      memcpy(mBackBufferV->Data() + i * mBackBufferV->Stride(),
+             data->mCrChannel + i * data->mCbCrStride,
+             data->mCbCrSize.width);
+    }
       
     YUVImage yuv(mBackBufferY->GetShmem(),
                  mBackBufferU->GetShmem(),
-                 mBackBufferV->GetShmem());
+                 mBackBufferV->GetShmem(),
+                 data->GetPictureRect());
   
     BasicManager()->PaintedImage(BasicManager()->Hold(this),
                                  yuv);
 
     return;
   }
 
   gfxIntSize oldSize = mSize;
diff --git a/gfx/layers/d3d10/ImageLayerD3D10.cpp b/gfx/layers/d3d10/ImageLayerD3D10.cpp
--- a/gfx/layers/d3d10/ImageLayerD3D10.cpp
+++ b/gfx/layers/d3d10/ImageLayerD3D10.cpp
@@ -343,103 +343,49 @@ ImageLayerD3D10::RenderLayer()
 
     effect()->GetVariableByName("vLayerQuad")->AsVector()->SetFloatVector(
       ShaderConstantRectD3D10(
         (float)0,
         (float)0,
         (float)yuvImage->mSize.width,
         (float)yuvImage->mSize.height)
       );
+
+    effect()->GetVariableByName("vTextureCoords")->AsVector()->SetFloatVector(
+      ShaderConstantRectD3D10(
+        (float)yuvImage->mData.mPicX / yuvImage->mData.mYSize.width,
+        (float)yuvImage->mData.mPicY / yuvImage->mData.mYSize.height,
+        (float)yuvImage->mData.mPicSize.width / yuvImage->mData.mYSize.width,
+        (float)yuvImage->mData.mPicSize.height / yuvImage->mData.mYSize.height)
+       );
   }
 
   technique->GetPassByIndex(0)->Apply(0);
   device()->Draw(4, 0);
 
+  if (image->GetFormat() == Image::PLANAR_YCBCR) {
+    effect()->GetVariableByName("vTextureCoords")->AsVector()->
+      SetFloatVector(ShaderConstantRectD3D10(0, 0, 1.0f, 1.0f));
+  }
+
   GetContainer()->NotifyPaintedImage(image);
 }
 
 PlanarYCbCrImageD3D10::PlanarYCbCrImageD3D10(ID3D10Device1 *aDevice)
   : PlanarYCbCrImage(static_cast<ImageD3D10*>(this))
   , mDevice(aDevice)
   , mHasData(PR_FALSE)
 {
 }
 
 void
 PlanarYCbCrImageD3D10::SetData(const PlanarYCbCrImage::Data &aData)
 {
-  // XXX - For D3D10Ex we really should just copy to systemmem surfaces here.
-  // For now, we copy the data
-  int width_shift = 0;
-  int height_shift = 0;
-  if (aData.mYSize.width == aData.mCbCrSize.width &&
-      aData.mYSize.height == aData.mCbCrSize.height) {
-     // YV24 format
-     width_shift = 0;
-     height_shift = 0;
-     mType = gfx::YV24;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height == aData.mCbCrSize.height) {
-    // YV16 format
-    width_shift = 1;
-    height_shift = 0;
-    mType = gfx::YV16;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height / 2 == aData.mCbCrSize.height ) {
-      // YV12 format
-    width_shift = 1;
-    height_shift = 1;
-    mType = gfx::YV12;
-  } else {
-    NS_ERROR("YCbCr format not supported");
-  }
-
-  mData = aData;
-  mData.mCbCrStride = mData.mCbCrSize.width = aData.mPicSize.width >> width_shift;
-  // Round up the values for width and height to make sure we sample enough data
-  // for the last pixel - See bug 590735
-  if (width_shift && (aData.mPicSize.width & 1)) {
-    mData.mCbCrStride++;
-    mData.mCbCrSize.width++;
-  }
-  mData.mCbCrSize.height = aData.mPicSize.height >> height_shift;
-  if (height_shift && (aData.mPicSize.height & 1)) {
-      mData.mCbCrSize.height++;
-  }
-  mData.mYSize = aData.mPicSize;
-  mData.mYStride = mData.mYSize.width;
-
-  mBuffer = new PRUint8[mData.mCbCrStride * mData.mCbCrSize.height * 2 +
-                        mData.mYStride * mData.mYSize.height];
-  mData.mYChannel = mBuffer;
-  mData.mCbChannel = mData.mYChannel + mData.mYStride * mData.mYSize.height;
-  mData.mCrChannel = mData.mCbChannel + mData.mCbCrStride * mData.mCbCrSize.height;
-
-  int cbcr_x = aData.mPicX >> width_shift;
-  int cbcr_y = aData.mPicY >> height_shift;
-
-  for (int i = 0; i < mData.mYSize.height; i++) {
-    memcpy(mData.mYChannel + i * mData.mYStride,
-           aData.mYChannel + ((aData.mPicY + i) * aData.mYStride) + aData.mPicX,
-           mData.mYStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCbChannel + i * mData.mCbCrStride,
-           aData.mCbChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCrChannel + i * mData.mCbCrStride,
-           aData.mCrChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-
-  // Fix picture rect to be correct
-  mData.mPicX = mData.mPicY = 0;
-  mSize = aData.mPicSize;
+  PRUint32 dummy;
+  mBuffer = CopyData(mData, mSize, dummy, aData);
 
   AllocateTextures();
 
   mHasData = PR_TRUE;
 }
 
 void
 PlanarYCbCrImageD3D10::AllocateTextures()
@@ -471,30 +417,36 @@ PlanarYCbCrImageD3D10::AllocateTextures(
   mDevice->CreateShaderResourceView(mCrTexture, NULL, getter_AddRefs(mCrView));
 }
 
 already_AddRefed<gfxASurface>
 PlanarYCbCrImageD3D10::GetAsSurface()
 {
   nsRefPtr<gfxImageSurface> imageSurface =
     new gfxImageSurface(mSize, gfxASurface::ImageFormatRGB24);
+  
+  gfx::YUVType type = 
+    gfx::TypeFromSize(mData.mYSize.width,
+                      mData.mYSize.height,
+                      mData.mCbCrSize.width,
+                      mData.mCbCrSize.height);
 
   // Convert from YCbCr to RGB now
   gfx::ConvertYCbCrToRGB32(mData.mYChannel,
                            mData.mCbChannel,
                            mData.mCrChannel,
                            imageSurface->Data(),
-                           0,
-                           0,
-                           mSize.width,
-                           mSize.height,
+                           mData.mPicX,
+                           mData.mPicY,
+                           mData.mPicSize.width,
+                           mData.mPicSize.height,
                            mData.mYStride,
                            mData.mCbCrStride,
                            imageSurface->Stride(),
-                           mType);
+                           type);
 
   return imageSurface.forget().get();
 }
 
 CairoImageD3D10::~CairoImageD3D10()
 {
 }
 
diff --git a/gfx/layers/d3d10/ImageLayerD3D10.h b/gfx/layers/d3d10/ImageLayerD3D10.h
--- a/gfx/layers/d3d10/ImageLayerD3D10.h
+++ b/gfx/layers/d3d10/ImageLayerD3D10.h
@@ -122,17 +122,16 @@ public:
   gfxIntSize mSize;
   nsRefPtr<ID3D10Texture2D> mYTexture;
   nsRefPtr<ID3D10Texture2D> mCrTexture;
   nsRefPtr<ID3D10Texture2D> mCbTexture;
   nsRefPtr<ID3D10ShaderResourceView> mYView;
   nsRefPtr<ID3D10ShaderResourceView> mCbView;
   nsRefPtr<ID3D10ShaderResourceView> mCrView;
   PRPackedBool mHasData;
-  gfx::YUVType mType; 
 };
 
 
 class THEBES_API CairoImageD3D10 : public CairoImage,
                                    public ImageD3D10
 {
 public:
   CairoImageD3D10(ID3D10Device1 *aDevice)
diff --git a/gfx/layers/d3d9/ImageLayerD3D9.cpp b/gfx/layers/d3d9/ImageLayerD3D9.cpp
--- a/gfx/layers/d3d9/ImageLayerD3D9.cpp
+++ b/gfx/layers/d3d9/ImageLayerD3D9.cpp
@@ -289,16 +289,25 @@ ImageLayerD3D9::RenderLayer()
 
     device()->SetVertexShaderConstantF(CBvLayerQuad,
                                        ShaderConstantRect(0,
                                                           0,
                                                           yuvImage->mSize.width,
                                                           yuvImage->mSize.height),
                                        1);
 
+    device()->SetVertexShaderConstantF(CBvTextureCoords,
+      ShaderConstantRect(
+        (float)yuvImage->mData.mPicX / yuvImage->mData.mYSize.width,
+        (float)yuvImage->mData.mPicY / yuvImage->mData.mYSize.height,
+        (float)yuvImage->mData.mPicSize.width / yuvImage->mData.mYSize.width,
+        (float)yuvImage->mData.mPicSize.height / yuvImage->mData.mYSize.height
+      ),
+      1);
+
     mD3DManager->SetShaderMode(DeviceManagerD3D9::YCBCRLAYER);
 
     /*
      * Send 3d control data and metadata
      */
     if (mD3DManager->GetNv3DVUtils()) {
       Nv_Stereo_Mode mode;
       switch (yuvImage->mData.mStereoMode) {
@@ -336,16 +345,19 @@ ImageLayerD3D9::RenderLayer()
     // presumably even with point filtering we'll still want chroma upsampling
     // to be linear. In the current approach we can't.
     device()->SetTexture(0, yuvImage->mYTexture);
     device()->SetTexture(1, yuvImage->mCbTexture);
     device()->SetTexture(2, yuvImage->mCrTexture);
 
     device()->DrawPrimitive(D3DPT_TRIANGLESTRIP, 0, 2);
 
+    device()->SetVertexShaderConstantF(CBvTextureCoords,
+      ShaderConstantRect(0, 0, 1.0f, 1.0f), 1);
+
   } else if (image->GetFormat() == Image::CAIRO_SURFACE) {
     CairoImageD3D9 *cairoImage =
       static_cast<CairoImageD3D9*>(image.get());
     ImageContainerD3D9 *container =
       static_cast<ImageContainerD3D9*>(GetContainer());
 
     if (container->device() != device()) {
       // Ensure future images get created with the right device.
@@ -388,85 +400,18 @@ PlanarYCbCrImageD3D9::PlanarYCbCrImageD3
   : PlanarYCbCrImage(static_cast<ImageD3D9*>(this))
   , mHasData(PR_FALSE)
 {
 }
 
 void
 PlanarYCbCrImageD3D9::SetData(const PlanarYCbCrImage::Data &aData)
 {
-  // XXX - For D3D9Ex we really should just copy to systemmem surfaces here.
-  // For now, we copy the data
-  int width_shift = 0;
-  int height_shift = 0;
-  if (aData.mYSize.width == aData.mCbCrSize.width &&
-      aData.mYSize.height == aData.mCbCrSize.height) {
-     // YV24 format
-     width_shift = 0;
-     height_shift = 0;
-     mType = gfx::YV24;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height == aData.mCbCrSize.height) {
-    // YV16 format
-    width_shift = 1;
-    height_shift = 0;
-    mType = gfx::YV16;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height / 2 == aData.mCbCrSize.height ) {
-      // YV12 format
-    width_shift = 1;
-    height_shift = 1;
-    mType = gfx::YV12;
-  } else {
-    NS_ERROR("YCbCr format not supported");
-  }
-
-  mData = aData;
-  mData.mCbCrStride = mData.mCbCrSize.width = aData.mPicSize.width >> width_shift;
-  // Round up the values for width and height to make sure we sample enough data
-  // for the last pixel - See bug 590735
-  if (width_shift && (aData.mPicSize.width & 1)) {
-    mData.mCbCrStride++;
-    mData.mCbCrSize.width++;
-  }
-  mData.mCbCrSize.height = aData.mPicSize.height >> height_shift;
-  if (height_shift && (aData.mPicSize.height & 1)) {
-      mData.mCbCrSize.height++;
-  }
-  mData.mYSize = aData.mPicSize;
-  mData.mYStride = mData.mYSize.width;
-
-  mBuffer = new PRUint8[mData.mCbCrStride * mData.mCbCrSize.height * 2 +
-                        mData.mYStride * mData.mYSize.height];
-  mData.mYChannel = mBuffer;
-  mData.mCbChannel = mData.mYChannel + mData.mYStride * mData.mYSize.height;
-  mData.mCrChannel = mData.mCbChannel + mData.mCbCrStride * mData.mCbCrSize.height;
-
-  int cbcr_x = aData.mPicX >> width_shift;
-  int cbcr_y = aData.mPicY >> height_shift;
-
-  for (int i = 0; i < mData.mYSize.height; i++) {
-    memcpy(mData.mYChannel + i * mData.mYStride,
-           aData.mYChannel + ((aData.mPicY + i) * aData.mYStride) + aData.mPicX,
-           mData.mYStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCbChannel + i * mData.mCbCrStride,
-           aData.mCbChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCrChannel + i * mData.mCbCrStride,
-           aData.mCrChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-
-  // Fix picture rect to be correct
-  mData.mPicX = mData.mPicY = 0;
-  mSize = aData.mPicSize;
+  PRUint32 dummy;
+  mBuffer = CopyData(mData, mSize, dummy, aData);
 
   mHasData = PR_TRUE;
 }
 
 void
 PlanarYCbCrImageD3D9::AllocateTextures(IDirect3DDevice9 *aDevice)
 {
   D3DLOCKED_RECT lockrectY;
@@ -589,30 +534,36 @@ PlanarYCbCrImageD3D9::FreeTextures()
 {
 }
 
 already_AddRefed<gfxASurface>
 PlanarYCbCrImageD3D9::GetAsSurface()
 {
   nsRefPtr<gfxImageSurface> imageSurface =
     new gfxImageSurface(mSize, gfxASurface::ImageFormatRGB24);
+  
+  gfx::YUVType type = 
+    gfx::TypeFromSize(mData.mYSize.width,
+                      mData.mYSize.height,
+                      mData.mCbCrSize.width,
+                      mData.mCbCrSize.height);
 
   // Convert from YCbCr to RGB now
   gfx::ConvertYCbCrToRGB32(mData.mYChannel,
                            mData.mCbChannel,
                            mData.mCrChannel,
                            imageSurface->Data(),
-                           0,
-                           0,
-                           mSize.width,
-                           mSize.height,
+                           mData.mPicX,
+                           mData.mPicY,
+                           mData.mPicSize.width,
+                           mData.mPicSize.height,
                            mData.mYStride,
                            mData.mCbCrStride,
                            imageSurface->Stride(),
-                           mType);
+                           type);
 
   return imageSurface.forget().get();
 }
 
 CairoImageD3D9::~CairoImageD3D9()
 {
 }
 
diff --git a/gfx/layers/d3d9/ImageLayerD3D9.h b/gfx/layers/d3d9/ImageLayerD3D9.h
--- a/gfx/layers/d3d9/ImageLayerD3D9.h
+++ b/gfx/layers/d3d9/ImageLayerD3D9.h
@@ -129,17 +129,16 @@ public:
   nsAutoArrayPtr<PRUint8> mBuffer;
   LayerManagerD3D9 *mManager;
   Data mData;
   gfxIntSize mSize;
   nsRefPtr<IDirect3DTexture9> mYTexture;
   nsRefPtr<IDirect3DTexture9> mCrTexture;
   nsRefPtr<IDirect3DTexture9> mCbTexture;
   PRPackedBool mHasData;
-  gfx::YUVType mType; 
 };
 
 
 class THEBES_API CairoImageD3D9 : public CairoImage,
                                   public ImageD3D9
 {
 public:
   CairoImageD3D9(IDirect3DDevice9 *aDevice)
diff --git a/gfx/layers/ipc/PLayers.ipdl b/gfx/layers/ipc/PLayers.ipdl
--- a/gfx/layers/ipc/PLayers.ipdl
+++ b/gfx/layers/ipc/PLayers.ipdl
@@ -82,16 +82,17 @@ union SurfaceDescriptor {
   Shmem;
   SurfaceDescriptorX11;
 };
 
 struct YUVImage {
   Shmem Ydata;
   Shmem Udata;
   Shmem Vdata;
+  nsIntRect picture;
 };
 
 union SharedImage {
   SurfaceDescriptor;
   YUVImage;
 };
 
 struct ThebesBuffer {
diff --git a/gfx/layers/opengl/ImageLayerOGL.cpp b/gfx/layers/opengl/ImageLayerOGL.cpp
--- a/gfx/layers/opengl/ImageLayerOGL.cpp
+++ b/gfx/layers/opengl/ImageLayerOGL.cpp
@@ -271,33 +271,39 @@ ImageContainerOGL::GetCurrentAsSurface(g
   if (mActiveImage->GetFormat() == Image::PLANAR_YCBCR) {
     PlanarYCbCrImageOGL *yuvImage =
       static_cast<PlanarYCbCrImageOGL*>(mActiveImage.get());
     if (!yuvImage->HasData()) {
       *aSize = gfxIntSize(0, 0);
       return nsnull;
     }
 
-    size = yuvImage->mSize;
+    size = yuvImage->mData.mPicSize;
 
     nsRefPtr<gfxImageSurface> imageSurface =
       new gfxImageSurface(size, gfxASurface::ImageFormatRGB24);
+  
+    gfx::YUVType type = 
+      gfx::TypeFromSize(yuvImage->mData.mYSize.width,
+                        yuvImage->mData.mYSize.height,
+                        yuvImage->mData.mCbCrSize.width,
+                        yuvImage->mData.mCbCrSize.height);
 
     gfx::ConvertYCbCrToRGB32(yuvImage->mData.mYChannel,
                              yuvImage->mData.mCbChannel,
                              yuvImage->mData.mCrChannel,
                              imageSurface->Data(),
-                             0,
-                             0,
+                             yuvImage->mData.mPicX,
+                             yuvImage->mData.mPicY,
                              size.width,
                              size.height,
                              yuvImage->mData.mYStride,
                              yuvImage->mData.mCbCrStride,
                              imageSurface->Stride(),
-                             yuvImage->mType);
+                             type);
 
     *aSize = size;
     return imageSurface.forget().get();
   }
 
   if (mActiveImage->GetFormat() == Image::CAIRO_SURFACE) {
     CairoImageOGL *cairoImage =
       static_cast<CairoImageOGL*>(mActiveImage.get());
@@ -427,17 +433,20 @@ ImageLayerOGL::RenderLayer(int,
     program->SetLayerQuadRect(nsIntRect(0, 0,
                                         yuvImage->mSize.width,
                                         yuvImage->mSize.height));
     program->SetLayerTransform(GetEffectiveTransform());
     program->SetLayerOpacity(GetEffectiveOpacity());
     program->SetRenderOffset(aOffset);
     program->SetYCbCrTextureUnits(0, 1, 2);
 
-    mOGLManager->BindAndDrawQuad(program);
+    mOGLManager->BindAndDrawQuadWithTextureRect(program,
+                                                yuvImage->mData.GetPictureRect(),
+                                                nsIntSize(yuvImage->mData.mYSize.width,
+                                                          yuvImage->mData.mYSize.height));
 
     // We shouldn't need to do this, but do it anyway just in case
     // someone else forgets.
     gl()->fActiveTexture(LOCAL_GL_TEXTURE0);
   } else if (image->GetFormat() == Image::CAIRO_SURFACE) {
     CairoImageOGL *cairoImage =
       static_cast<CairoImageOGL*>(image.get());
 
@@ -661,94 +670,21 @@ PlanarYCbCrImageOGL::~PlanarYCbCrImageOG
     mRecycleBin->RecycleTexture(&mTextures[1], RecycleBin::TEXTURE_C, mData.mCbCrSize);
     mRecycleBin->RecycleTexture(&mTextures[2], RecycleBin::TEXTURE_C, mData.mCbCrSize);
   }
 }
 
 void
 PlanarYCbCrImageOGL::SetData(const PlanarYCbCrImage::Data &aData)
 {
-  // For now, we copy the data
-  int width_shift = 0;
-  int height_shift = 0;
-  if (aData.mYSize.width == aData.mCbCrSize.width &&
-      aData.mYSize.height == aData.mCbCrSize.height) {
-     // YV24 format
-     width_shift = 0;
-     height_shift = 0;
-     mType = gfx::YV24;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height == aData.mCbCrSize.height) {
-    // YV16 format
-    width_shift = 1;
-    height_shift = 0;
-    mType = gfx::YV16;
-  } else if (aData.mYSize.width / 2 == aData.mCbCrSize.width &&
-             aData.mYSize.height / 2 == aData.mCbCrSize.height ) {
-      // YV12 format
-    width_shift = 1;
-    height_shift = 1;
-    mType = gfx::YV12;
-  } else {
-    NS_ERROR("YCbCr format not supported");
-  }
-  
-  mData = aData;
-  mData.mCbCrStride = mData.mCbCrSize.width = aData.mPicSize.width >> width_shift;
-  // Round up the values for width and height to make sure we sample enough data
-  // for the last pixel - See bug 590735
-  if (width_shift && (aData.mPicSize.width & 1)) {
-    mData.mCbCrStride++;
-    mData.mCbCrSize.width++;
-  }
-  mData.mCbCrSize.height = aData.mPicSize.height >> height_shift;
-  if (height_shift && (aData.mPicSize.height & 1)) {
-      mData.mCbCrSize.height++;
-  }
-  mData.mYSize = aData.mPicSize;
-  mData.mYStride = mData.mYSize.width;
-
   // Recycle the previous image main-memory buffer now that we're about to get a new buffer
   if (mBuffer)
     mRecycleBin->RecycleBuffer(mBuffer.forget(), mBufferSize);
-
-  // update buffer size
-  mBufferSize = mData.mCbCrStride * mData.mCbCrSize.height * 2 +
-                mData.mYStride * mData.mYSize.height;
-
-  // get new buffer
-  mBuffer = mRecycleBin->GetBuffer(mBufferSize);
-  if (!mBuffer)
-    return;
-
-  mData.mYChannel = mBuffer;
-  mData.mCbChannel = mData.mYChannel + mData.mYStride * mData.mYSize.height;
-  mData.mCrChannel = mData.mCbChannel + mData.mCbCrStride * mData.mCbCrSize.height;
-  int cbcr_x = aData.mPicX >> width_shift;
-  int cbcr_y = aData.mPicY >> height_shift;
-
-  for (int i = 0; i < mData.mYSize.height; i++) {
-    memcpy(mData.mYChannel + i * mData.mYStride,
-           aData.mYChannel + ((aData.mPicY + i) * aData.mYStride) + aData.mPicX,
-           mData.mYStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCbChannel + i * mData.mCbCrStride,
-           aData.mCbChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-  for (int i = 0; i < mData.mCbCrSize.height; i++) {
-    memcpy(mData.mCrChannel + i * mData.mCbCrStride,
-           aData.mCrChannel + ((cbcr_y + i) * aData.mCbCrStride) + cbcr_x,
-           mData.mCbCrStride);
-  }
-
-  // Fix picture rect to be correct
-  mData.mPicX = mData.mPicY = 0;
-  mSize = aData.mPicSize;
+  
+  mBuffer = CopyData(mData, mSize, mBufferSize, aData);
 
   mHasData = PR_TRUE;
 }
 
 void
 PlanarYCbCrImageOGL::AllocateTextures(mozilla::gl::GLContext *gl)
 {
   gl->MakeCurrent();
@@ -764,70 +700,38 @@ PlanarYCbCrImageOGL::AllocateTextures(mo
 }
 
 static void
 UploadYUVToTexture(GLContext* gl, const PlanarYCbCrImage::Data& aData, 
                    GLTexture* aYTexture,
                    GLTexture* aUTexture,
                    GLTexture* aVTexture)
 {
-  GLint alignment;
-
-  if (!((ptrdiff_t)aData.mYStride & 0x7) && !((ptrdiff_t)aData.mYChannel & 0x7)) {
-    alignment = 8;
-  } else if (!((ptrdiff_t)aData.mYStride & 0x3)) {
-    alignment = 4;
-  } else if (!((ptrdiff_t)aData.mYStride & 0x1)) {
-    alignment = 2;
-  } else {
-    alignment = 1;
-  }
-
-  // Set texture alignment for Y plane.
-  gl->fPixelStorei(LOCAL_GL_UNPACK_ALIGNMENT, alignment);
-
-  gl->fBindTexture(LOCAL_GL_TEXTURE_2D, aYTexture->GetTextureID());
-  gl->fTexSubImage2D(LOCAL_GL_TEXTURE_2D, 0,
-                     0, 0, aData.mYSize.width, aData.mYSize.height,
-                     LOCAL_GL_LUMINANCE,
-                     LOCAL_GL_UNSIGNED_BYTE,
-                     aData.mYChannel);
+  nsIntRect size(0, 0, aData.mYSize.width, aData.mYSize.height);
+  GLuint texture = aYTexture->GetTextureID();
+  nsRefPtr<gfxASurface> surf = new gfxImageSurface(aData.mYChannel,
+                                                   aData.mYSize,
+                                                   aData.mYStride,
+                                                   gfxASurface::ImageFormatA8);
+  gl->UploadSurfaceToTexture(surf, size, texture, true);
+  
+  size = nsIntRect(0, 0, aData.mCbCrSize.width, aData.mCbCrSize.height);
+  texture = aUTexture->GetTextureID();
+  surf = new gfxImageSurface(aData.mCbChannel,
+                             aData.mCbCrSize,
+                             aData.mCbCrStride,
+                             gfxASurface::ImageFormatA8);
+  gl->UploadSurfaceToTexture(surf, size, texture, true);
 
-  if (!((ptrdiff_t)aData.mCbCrStride & 0x7) && 
-      !((ptrdiff_t)aData.mCbChannel & 0x7) &&
-      !((ptrdiff_t)aData.mCrChannel & 0x7))
-  {
-    alignment = 8;
-  } else if (!((ptrdiff_t)aData.mCbCrStride & 0x3)) {
-    alignment = 4;
-  } else if (!((ptrdiff_t)aData.mCbCrStride & 0x1)) {
-    alignment = 2;
-  } else {
-    alignment = 1;
-  }
-  
-  // Set texture alignment for Cb/Cr plane
-  gl->fPixelStorei(LOCAL_GL_UNPACK_ALIGNMENT, alignment);
-
-  gl->fBindTexture(LOCAL_GL_TEXTURE_2D, aUTexture->GetTextureID());
-  gl->fTexSubImage2D(LOCAL_GL_TEXTURE_2D, 0,
-                     0, 0, aData.mCbCrSize.width, aData.mCbCrSize.height,
-                     LOCAL_GL_LUMINANCE,
-                     LOCAL_GL_UNSIGNED_BYTE,
-                     aData.mCbChannel);
-
-  gl->fBindTexture(LOCAL_GL_TEXTURE_2D, aVTexture->GetTextureID());
-  gl->fTexSubImage2D(LOCAL_GL_TEXTURE_2D, 0,
-                     0, 0, aData.mCbCrSize.width, aData.mCbCrSize.height,
-                     LOCAL_GL_LUMINANCE,
-                     LOCAL_GL_UNSIGNED_BYTE,
-                     aData.mCrChannel);
-
-  // Reset alignment to default
-  gl->fPixelStorei(LOCAL_GL_UNPACK_ALIGNMENT, 4);
+  texture = aVTexture->GetTextureID();
+  surf = new gfxImageSurface(aData.mCrChannel,
+                             aData.mCbCrSize,
+                             aData.mCbCrStride,
+                             gfxASurface::ImageFormatA8);
+  gl->UploadSurfaceToTexture(surf, size, texture, true);
 }
 
 void
 PlanarYCbCrImageOGL::UpdateTextures(GLContext *gl)
 {
   if (!mBuffer || !mHasData)
     return;
 
@@ -976,16 +880,19 @@ ShadowImageLayerOGL::Swap(const SharedIm
       const YUVImage& yuv = aNewFront.get_YUVImage();
     
       nsRefPtr<gfxSharedImageSurface> surfY =
         gfxSharedImageSurface::Open(yuv.Ydata());
       nsRefPtr<gfxSharedImageSurface> surfU =
         gfxSharedImageSurface::Open(yuv.Udata());
       nsRefPtr<gfxSharedImageSurface> surfV =
         gfxSharedImageSurface::Open(yuv.Vdata());
+
+      mPictureRect = yuv.picture();
+      mSize = surfY->GetSize();
  
       PlanarYCbCrImage::Data data;
       data.mYChannel = surfY->Data();
       data.mYStride = surfY->Stride();
       data.mYSize = surfY->GetSize();
       data.mCbChannel = surfU->Data();
       data.mCrChannel = surfV->Data();
       data.mCbCrStride = surfU->Stride();
@@ -1055,21 +962,30 @@ ShadowImageLayerOGL::RenderLayer(int aPr
     gl()->fActiveTexture(LOCAL_GL_TEXTURE2);
     gl()->fBindTexture(LOCAL_GL_TEXTURE_2D, mYUVTexture[2].GetTextureID());
     ApplyFilter(mFilter);
     
     YCbCrTextureLayerProgram *yuvProgram = mOGLManager->GetYCbCrLayerProgram();
 
     yuvProgram->Activate();
     yuvProgram->SetLayerQuadRect(nsIntRect(0, 0,
-                                           mSize.width,
-                                           mSize.height));
+                                           mPictureRect.width,
+                                           mPictureRect.height));
     yuvProgram->SetYCbCrTextureUnits(0, 1, 2);
 
     program = yuvProgram;
+    program->SetLayerTransform(GetEffectiveTransform());
+    program->SetLayerOpacity(GetEffectiveOpacity());
+    program->SetRenderOffset(aOffset);
+
+    mOGLManager->BindAndDrawQuadWithTextureRect(program,
+                                                mPictureRect,
+                                                nsIntSize(mSize.width, mSize.height));
+
+    return;
   }
 
   program->SetLayerTransform(GetEffectiveTransform());
   program->SetLayerOpacity(GetEffectiveOpacity());
   program->SetRenderOffset(aOffset);
 
   mOGLManager->BindAndDrawQuad(program);
 }
diff --git a/gfx/layers/opengl/ImageLayerOGL.h b/gfx/layers/opengl/ImageLayerOGL.h
--- a/gfx/layers/opengl/ImageLayerOGL.h
+++ b/gfx/layers/opengl/ImageLayerOGL.h
@@ -202,24 +202,27 @@ public:
 
   PRBool HasData() { return mHasData; }
   PRBool HasTextures()
   {
     return mTextures[0].IsAllocated() && mTextures[1].IsAllocated() &&
            mTextures[2].IsAllocated();
   }
 
+  PRUint8* AllocateBuffer(PRUint32 aSize) {
+    return mRecycleBin->GetBuffer(aSize);
+  }
+
   nsAutoArrayPtr<PRUint8> mBuffer;
   PRUint32 mBufferSize;
   nsRefPtr<RecycleBin> mRecycleBin;
   GLTexture mTextures[3];
   Data mData;
   gfxIntSize mSize;
   PRPackedBool mHasData;
-  gfx::YUVType mType; 
 };
 
 
 class THEBES_API CairoImageOGL : public CairoImage
 {
   typedef mozilla::gl::GLContext GLContext;
 
 public:
@@ -263,13 +266,14 @@ public:
 
   virtual void RenderLayer(int aPreviousFrameBuffer,
                            const nsIntPoint& aOffset);
 
 private:
   nsRefPtr<TextureImage> mTexImage;
   GLTexture mYUVTexture[3];
   gfxIntSize mSize;
+  nsIntRect mPictureRect;
 };
 
 } /* layers */
 } /* mozilla */
 #endif /* GFX_IMAGELAYEROGL_H */
diff --git a/gfx/layers/opengl/LayerManagerOGL.cpp b/gfx/layers/opengl/LayerManagerOGL.cpp
--- a/gfx/layers/opengl/LayerManagerOGL.cpp
+++ b/gfx/layers/opengl/LayerManagerOGL.cpp
@@ -665,16 +665,81 @@ LayerManagerOGL::FPSState::DrawFPS(GLCon
   context->fVertexAttribPointer(tcattr,
                                 2, LOCAL_GL_FLOAT,
                                 LOCAL_GL_FALSE,
                                 0, texCoords);
 
   context->fDrawArrays(LOCAL_GL_TRIANGLE_STRIP, 0, 12);
 }
 
+// |aTexCoordRect| is the rectangle from the texture that we want to
+// draw using the given program.  The program already has a necessary
+// offset and scale, so the geometry that needs to be drawn is a unit
+// square from 0,0 to 1,1.
+//
+// |aTexSize| is the actual size of the texture, as it can be larger
+// than the rectangle given by |aTexCoordRect|.
+void 
+LayerManagerOGL::BindAndDrawQuadWithTextureRect(LayerProgram *aProg,
+                                                const nsIntRect& aTexCoordRect,
+                                                const nsIntSize& aTexSize,
+                                                GLenum aWrapMode)
+{
+  GLuint vertAttribIndex =
+    aProg->AttribLocation(LayerProgram::VertexAttrib);
+  GLuint texCoordAttribIndex =
+    aProg->AttribLocation(LayerProgram::TexCoordAttrib);
+  NS_ASSERTION(texCoordAttribIndex != GLuint(-1), "no texture coords?");
+
+  // clear any bound VBO so that glVertexAttribPointer() goes back to
+  // "pointer mode"
+  mGLContext->fBindBuffer(LOCAL_GL_ARRAY_BUFFER, 0);
+
+  // Given what we know about these textures and coordinates, we can
+  // compute fmod(t, 1.0f) to get the same texture coordinate out.  If
+  // the texCoordRect dimension is < 0 or > width/height, then we have
+  // wraparound that we need to deal with by drawing multiple quads,
+  // because we can't rely on full non-power-of-two texture support
+  // (which is required for the REPEAT wrap mode).
+
+  GLContext::RectTriangles rects;
+
+  if (aWrapMode == LOCAL_GL_REPEAT) {
+    rects.addRect(/* dest rectangle */
+                  0.0f, 0.0f, 1.0f, 1.0f,
+                  /* tex coords */
+                  aTexCoordRect.x / GLfloat(aTexSize.width),
+                  aTexCoordRect.y / GLfloat(aTexSize.height),
+                  aTexCoordRect.XMost() / GLfloat(aTexSize.width),
+                  aTexCoordRect.YMost() / GLfloat(aTexSize.height));
+  } else {
+    GLContext::DecomposeIntoNoRepeatTriangles(aTexCoordRect, aTexSize, rects);
+  }
+
+  mGLContext->fVertexAttribPointer(vertAttribIndex, 2,
+                                   LOCAL_GL_FLOAT, LOCAL_GL_FALSE, 0,
+                                   rects.vertexPointer());
+
+  mGLContext->fVertexAttribPointer(texCoordAttribIndex, 2,
+                                   LOCAL_GL_FLOAT, LOCAL_GL_FALSE, 0,
+                                   rects.texCoordPointer());
+
+  {
+    mGLContext->fEnableVertexAttribArray(texCoordAttribIndex);
+    {
+      mGLContext->fEnableVertexAttribArray(vertAttribIndex);
+
+      mGLContext->fDrawArrays(LOCAL_GL_TRIANGLES, 0, rects.elements());
+
+      mGLContext->fDisableVertexAttribArray(vertAttribIndex);
+    }
+    mGLContext->fDisableVertexAttribArray(texCoordAttribIndex);
+  }
+}
+
 void
 LayerManagerOGL::Render()
 {
   if (mDestroyed) {
     NS_WARNING("Call on destroyed layer manager");
     return;
   }
 
diff --git a/gfx/layers/opengl/LayerManagerOGL.h b/gfx/layers/opengl/LayerManagerOGL.h
--- a/gfx/layers/opengl/LayerManagerOGL.h
+++ b/gfx/layers/opengl/LayerManagerOGL.h
@@ -355,16 +355,22 @@ public:
   void BindAndDrawQuad(LayerProgram *aProg,
                        bool aFlipped = false)
   {
     BindAndDrawQuad(aProg->AttribLocation(LayerProgram::VertexAttrib),
                     aProg->AttribLocation(LayerProgram::TexCoordAttrib),
                     aFlipped);
   }
 
+  void BindAndDrawQuadWithTextureRect(LayerProgram *aProg,
+                                      const nsIntRect& aTexCoordRect,
+                                      const nsIntSize& aTexSize,
+                                      GLenum aWrapMode = LOCAL_GL_REPEAT);
+                                      
+
 #ifdef MOZ_LAYERS_HAVE_LOG
   virtual const char* Name() const { return "OGL"; }
 #endif // MOZ_LAYERS_HAVE_LOG
 
   const nsIntSize& GetWigetSize() {
     return mWidgetSize;
   }
 
diff --git a/gfx/layers/opengl/ThebesLayerOGL.cpp b/gfx/layers/opengl/ThebesLayerOGL.cpp
--- a/gfx/layers/opengl/ThebesLayerOGL.cpp
+++ b/gfx/layers/opengl/ThebesLayerOGL.cpp
@@ -70,84 +70,16 @@ CreateClampOrRepeatTextureImage(GLContex
        aGl->IsExtensionSupported(GLContext::OES_texture_npot)))
   {
     wrapMode = LOCAL_GL_REPEAT;
   }
 
   return aGl->CreateTextureImage(aSize, aContentType, wrapMode);
 }
 
-// |aTexCoordRect| is the rectangle from the texture that we want to
-// draw using the given program.  The program already has a necessary
-// offset and scale, so the geometry that needs to be drawn is a unit
-// square from 0,0 to 1,1.
-//
-// |aTexSize| is the actual size of the texture, as it can be larger
-// than the rectangle given by |aTexCoordRect|.
-static void
-BindAndDrawQuadWithTextureRect(GLContext* aGl,
-                               LayerProgram *aProg,
-                               const nsIntRect& aTexCoordRect,
-                               const nsIntSize& aTexSize,
-                               GLenum aWrapMode)
-{
-  GLuint vertAttribIndex =
-    aProg->AttribLocation(LayerProgram::VertexAttrib);
-  GLuint texCoordAttribIndex =
-    aProg->AttribLocation(LayerProgram::TexCoordAttrib);
-  NS_ASSERTION(texCoordAttribIndex != GLuint(-1), "no texture coords?");
-
-  // clear any bound VBO so that glVertexAttribPointer() goes back to
-  // "pointer mode"
-  aGl->fBindBuffer(LOCAL_GL_ARRAY_BUFFER, 0);
-
-  // Given what we know about these textures and coordinates, we can
-  // compute fmod(t, 1.0f) to get the same texture coordinate out.  If
-  // the texCoordRect dimension is < 0 or > width/height, then we have
-  // wraparound that we need to deal with by drawing multiple quads,
-  // because we can't rely on full non-power-of-two texture support
-  // (which is required for the REPEAT wrap mode).
-
-  GLContext::RectTriangles rects;
-
-  if (aWrapMode == LOCAL_GL_REPEAT) {
-    rects.addRect(/* dest rectangle */
-                  0.0f, 0.0f, 1.0f, 1.0f,
-                  /* tex coords */
-                  aTexCoordRect.x / GLfloat(aTexSize.width),
-                  aTexCoordRect.y / GLfloat(aTexSize.height),
-                  aTexCoordRect.XMost() / GLfloat(aTexSize.width),
-                  aTexCoordRect.YMost() / GLfloat(aTexSize.height));
-  } else {
-    GLContext::DecomposeIntoNoRepeatTriangles(aTexCoordRect, aTexSize, rects);
-  }
-
-  // vertex position buffer is 2 floats, not normalized, 0 stride.
-  aGl->fVertexAttribPointer(vertAttribIndex, 2,
-                            LOCAL_GL_FLOAT, LOCAL_GL_FALSE, 0,
-                            rects.vertexPointer());
-
-  // texture coord buffer is 2 floats, not normalized, 0 stride.
-  aGl->fVertexAttribPointer(texCoordAttribIndex, 2,
-                            LOCAL_GL_FLOAT, LOCAL_GL_FALSE, 0,
-                            rects.texCoordPointer());
-
-  {
-    aGl->fEnableVertexAttribArray(texCoordAttribIndex);
-    {
-      aGl->fEnableVertexAttribArray(vertAttribIndex);
-
-      aGl->fDrawArrays(LOCAL_GL_TRIANGLES, 0, rects.elements());
-
-      aGl->fDisableVertexAttribArray(vertAttribIndex);
-    }
-    aGl->fDisableVertexAttribArray(texCoordAttribIndex);
-  }
-}
-
 static void
 SetAntialiasingFlags(Layer* aLayer, gfxContext* aTarget)
 {
   nsRefPtr<gfxASurface> surface = aTarget->CurrentSurface();
   if (surface->GetContentType() != gfxASurface::CONTENT_COLOR_ALPHA) {
     // Destination doesn't have alpha channel; no need to set any special flags
     return;
   }
@@ -264,19 +196,19 @@ ThebesLayerBufferOGL::RenderTo(const nsI
     }
     nsIntRegionRectIterator iter(*renderRegion);
     while (const nsIntRect *iterRect = iter.Next()) {
       nsIntRect quadRect = *iterRect;
       program->SetLayerQuadRect(quadRect);
 
       quadRect.MoveBy(-GetOriginOffset());
 
-      BindAndDrawQuadWithTextureRect(gl(), program, quadRect,
-                                     mTexImage->GetSize(),
-                                     mTexImage->GetWrapMode());
+      aManager->BindAndDrawQuadWithTextureRect(program, quadRect,
+                                               mTexImage->GetSize(),
+                                               mTexImage->GetWrapMode());
     }
   }
 
   if (mTexImageOnWhite) {
     // Restore defaults
     gl()->fBlendFuncSeparate(LOCAL_GL_ONE, LOCAL_GL_ONE_MINUS_SRC_ALPHA,
                              LOCAL_GL_ONE, LOCAL_GL_ONE);
   }
diff --git a/gfx/thebes/GLContext.cpp b/gfx/thebes/GLContext.cpp
--- a/gfx/thebes/GLContext.cpp
+++ b/gfx/thebes/GLContext.cpp
@@ -1377,17 +1377,18 @@ GLContext::UploadSurfaceToTexture(gfxASu
     }
 
     nsRefPtr<gfxImageSurface> imageSurface = aSurface->GetAsImageSurface();
     unsigned char* data = NULL;
 
     if (!imageSurface || 
         (imageSurface->Format() != gfxASurface::ImageFormatARGB32 &&
          imageSurface->Format() != gfxASurface::ImageFormatRGB24 &&
-         imageSurface->Format() != gfxASurface::ImageFormatRGB16_565)) {
+         imageSurface->Format() != gfxASurface::ImageFormatRGB16_565 &&
+         imageSurface->Format() != gfxASurface::ImageFormatA8)) {
         // We can't get suitable pixel data for the surface, make a copy
         nsIntRect bounds = aDstRegion.GetBounds();
         imageSurface = 
           new gfxImageSurface(gfxIntSize(bounds.width, bounds.height), 
                               gfxASurface::ImageFormatARGB32);
   
         nsRefPtr<gfxContext> context = new gfxContext(imageSurface);
 
@@ -1425,16 +1426,22 @@ GLContext::UploadSurfaceToTexture(gfxASu
             type = LOCAL_GL_UNSIGNED_BYTE;
             shader = BGRXLayerProgramType;
             break;
         case gfxASurface::ImageFormatRGB16_565:
             format = LOCAL_GL_RGB;
             type = LOCAL_GL_UNSIGNED_SHORT_5_6_5;
             shader = RGBALayerProgramType;
             break;
+        case gfxASurface::ImageFormatA8:
+            format = LOCAL_GL_LUMINANCE;
+            type = LOCAL_GL_UNSIGNED_BYTE;
+            // We don't have a specific luminance shader
+            shader = ShaderProgramType(0);
+            break;
         default:
             NS_ASSERTION(false, "Unhandled image surface format!");
             format = 0;
             type = 0;
             shader = ShaderProgramType(0);
     }
 
 #ifndef USE_GLES2
diff --git a/gfx/ycbcr/README b/gfx/ycbcr/README
--- a/gfx/ycbcr/README
+++ b/gfx/ycbcr/README
@@ -18,8 +18,10 @@ convert.patch contains the following cha
   * Change Chromium code to allow a picture region.
   * The YUV conversion will convert within this picture region only.
   * Add YCbCr 4:4:4 support
   * Bug 619178 - Update CPU detection in yuv_convert to new SSE.h interface.
   * Bug 616778 - Split yuv_convert FilterRows vectorized code into separate files so it can
     be properly guarded with cpuid() calls.
 
 win64.patch: SSE2 optimization for Microsoft Visual C++ x64 version
+
+TypeFromSize.patch: Bug 656185 - Add a method to detect YUVType from plane sizes.
diff --git a/gfx/ycbcr/TypeFromSize.patch b/gfx/ycbcr/TypeFromSize.patch
new file mode 100644
--- /dev/null
+++ b/gfx/ycbcr/TypeFromSize.patch
@@ -0,0 +1,58 @@
+diff --git a/gfx/ycbcr/yuv_convert.cpp b/gfx/ycbcr/yuv_convert.cpp
+--- a/gfx/ycbcr/yuv_convert.cpp
++++ b/gfx/ycbcr/yuv_convert.cpp
+@@ -26,16 +26,32 @@ namespace mozilla {
+ 
+ namespace gfx {
+  
+ // 16.16 fixed point arithmetic
+ const int kFractionBits = 16;
+ const int kFractionMax = 1 << kFractionBits;
+ const int kFractionMask = ((1 << kFractionBits) - 1);
+ 
++NS_GFX_(YUVType) TypeFromSize(int ywidth, 
++                              int yheight, 
++                              int cbcrwidth, 
++                              int cbcrheight)
++{
++  if (ywidth == cbcrwidth && yheight == cbcrheight) {
++    return YV24;
++  }
++  else if (ywidth / 2 == cbcrwidth && yheight == cbcrheight) {
++    return YV16;
++  }
++  else {
++    return YV12;
++  }
++}
++
+ // Convert a frame of YUV to 32 bit ARGB.
+ NS_GFX_(void) ConvertYCbCrToRGB32(const uint8* y_buf,
+                                   const uint8* u_buf,
+                                   const uint8* v_buf,
+                                   uint8* rgb_buf,
+                                   int pic_x,
+                                   int pic_y,
+                                   int pic_width,
+diff --git a/gfx/ycbcr/yuv_convert.h b/gfx/ycbcr/yuv_convert.h
+--- a/gfx/ycbcr/yuv_convert.h
++++ b/gfx/ycbcr/yuv_convert.h
+@@ -36,16 +36,18 @@ enum Rotate {
+ // Filter affects how scaling looks.
+ enum ScaleFilter {
+   FILTER_NONE = 0,        // No filter (point sampled).
+   FILTER_BILINEAR_H = 1,  // Bilinear horizontal filter.
+   FILTER_BILINEAR_V = 2,  // Bilinear vertical filter.
+   FILTER_BILINEAR = 3     // Bilinear filter.
+ };
+ 
++NS_GFX_(YUVType) TypeFromSize(int ywidth, int yheight, int cbcrwidth, int cbcrheight);
++
+ // Convert a frame of YUV to 32 bit ARGB.
+ // Pass in YV16/YV12 depending on source format
+ NS_GFX_(void) ConvertYCbCrToRGB32(const uint8* yplane,
+                                   const uint8* uplane,
+                                   const uint8* vplane,
+                                   uint8* rgbframe,
+                                   int pic_x,
+                                   int pic_y,
diff --git a/gfx/ycbcr/update.sh b/gfx/ycbcr/update.sh
--- a/gfx/ycbcr/update.sh
+++ b/gfx/ycbcr/update.sh
@@ -3,8 +3,9 @@ cp $1/media/base/yuv_convert.h .
 cp $1/media/base/yuv_convert.cc yuv_convert.cpp
 cp $1/media/base/yuv_row.h .
 cp $1/media/base/yuv_row_table.cc yuv_row_table.cpp
 cp $1/media/base/yuv_row_posix.cc yuv_row_posix.cpp
 cp $1/media/base/yuv_row_win.cc yuv_row_win.cpp
 cp $1/media/base/yuv_row_posix.cc yuv_row_c.cpp
 patch -p3 <convert.patch
 patch -p3 <win64.patch
+patch -p3 <TypeFromSize.patch
diff --git a/gfx/ycbcr/yuv_convert.cpp b/gfx/ycbcr/yuv_convert.cpp
--- a/gfx/ycbcr/yuv_convert.cpp
+++ b/gfx/ycbcr/yuv_convert.cpp
@@ -26,16 +26,32 @@ namespace mozilla {
 
 namespace gfx {
  
 // 16.16 fixed point arithmetic
 const int kFractionBits = 16;
 const int kFractionMax = 1 << kFractionBits;
 const int kFractionMask = ((1 << kFractionBits) - 1);
 
+NS_GFX_(YUVType) TypeFromSize(int ywidth, 
+                              int yheight, 
+                              int cbcrwidth, 
+                              int cbcrheight)
+{
+  if (ywidth == cbcrwidth && yheight == cbcrheight) {
+    return YV24;
+  }
+  else if (ywidth / 2 == cbcrwidth && yheight == cbcrheight) {
+    return YV16;
+  }
+  else {
+    return YV12;
+  }
+}
+
 // Convert a frame of YUV to 32 bit ARGB.
 NS_GFX_(void) ConvertYCbCrToRGB32(const uint8* y_buf,
                                   const uint8* u_buf,
                                   const uint8* v_buf,
                                   uint8* rgb_buf,
                                   int pic_x,
                                   int pic_y,
                                   int pic_width,
diff --git a/gfx/ycbcr/yuv_convert.h b/gfx/ycbcr/yuv_convert.h
--- a/gfx/ycbcr/yuv_convert.h
+++ b/gfx/ycbcr/yuv_convert.h
@@ -36,16 +36,18 @@ enum Rotate {
 // Filter affects how scaling looks.
 enum ScaleFilter {
   FILTER_NONE = 0,        // No filter (point sampled).
   FILTER_BILINEAR_H = 1,  // Bilinear horizontal filter.
   FILTER_BILINEAR_V = 2,  // Bilinear vertical filter.
   FILTER_BILINEAR = 3     // Bilinear filter.
 };
 
+NS_GFX_(YUVType) TypeFromSize(int ywidth, int yheight, int cbcrwidth, int cbcrheight);
+
 // Convert a frame of YUV to 32 bit ARGB.
 // Pass in YV16/YV12 depending on source format
 NS_GFX_(void) ConvertYCbCrToRGB32(const uint8* yplane,
                                   const uint8* uplane,
                                   const uint8* vplane,
                                   uint8* rgbframe,
                                   int pic_x,
                                   int pic_y,
diff --git a/netwerk/build/nsNetModule.cpp b/netwerk/build/nsNetModule.cpp
--- a/netwerk/build/nsNetModule.cpp
+++ b/netwerk/build/nsNetModule.cpp
@@ -278,31 +278,31 @@ NS_GENERIC_FACTORY_CONSTRUCTOR(nsViewSou
 #endif
 
 #ifdef NECKO_PROTOCOL_wyciwyg
 #include "nsWyciwygProtocolHandler.h"
 NS_GENERIC_FACTORY_CONSTRUCTOR(nsWyciwygProtocolHandler)
 #endif
 
 #ifdef NECKO_PROTOCOL_websocket
-#include "nsWebSocketHandler.h"
+#include "WebSocketChannel.h"
 #include "WebSocketChannelChild.h"
 namespace mozilla {
 namespace net {
 static BaseWebSocketChannel*
-WebSocketHandlerConstructor(bool aSecure)
+WebSocketChannelConstructor(bool aSecure)
 {
   if (IsNeckoChild()) {
     return new WebSocketChannelChild(aSecure);
   }
 
   if (aSecure) {
-    return new nsWebSocketSSLHandler;
+    return new WebSocketSSLChannel;
   } else {
-    return new nsWebSocketHandler;
+    return new WebSocketChannel;
   }
 }
 
 #define WEB_SOCKET_HANDLER_CONSTRUCTOR(type, secure)  \
 static nsresult                                       \
 type##Constructor(nsISupports *aOuter, REFNSIID aIID, \
                   void **aResult)                     \
 {                                                     \
@@ -310,25 +310,25 @@ type##Constructor(nsISupports *aOuter, R
                                                       \
   BaseWebSocketChannel * inst;                        \
                                                       \
   *aResult = NULL;                                    \
   if (NULL != aOuter) {                               \
     rv = NS_ERROR_NO_AGGREGATION;                     \
     return rv;                                        \
   }                                                   \
-  inst = WebSocketHandlerConstructor(secure);         \
+  inst = WebSocketChannelConstructor(secure);         \
   NS_ADDREF(inst);                                    \
   rv = inst->QueryInterface(aIID, aResult);           \
   NS_RELEASE(inst);                                   \
   return rv;                                          \
 }
 
-WEB_SOCKET_HANDLER_CONSTRUCTOR(nsWebSocketHandler, false)
-WEB_SOCKET_HANDLER_CONSTRUCTOR(nsWebSocketSSLHandler, true)
+WEB_SOCKET_HANDLER_CONSTRUCTOR(WebSocketChannel, false)
+WEB_SOCKET_HANDLER_CONSTRUCTOR(WebSocketSSLChannel, true)
 #undef WEB_SOCKET_HANDLER_CONSTRUCTOR
 } // namespace mozilla::net
 } // namespace mozilla
 #endif
 
 ///////////////////////////////////////////////////////////////////////////////
 
 #include "nsURIChecker.h"
@@ -670,17 +670,17 @@ static void nsNetShutdown()
     delete gNetStrings;
     gNetStrings = nsnull;
     
     // Release DNS service reference.
     nsDNSPrefetch::Shutdown();
 
 #ifdef NECKO_PROTOCOL_websocket
     // Release the Websocket Admission Manager
-    mozilla::net::nsWebSocketHandler::Shutdown();
+    mozilla::net::WebSocketChannel::Shutdown();
 #endif // NECKO_PROTOCOL_websocket
 }
 
 NS_DEFINE_NAMED_CID(NS_IOSERVICE_CID);
 NS_DEFINE_NAMED_CID(NS_STREAMTRANSPORTSERVICE_CID);
 NS_DEFINE_NAMED_CID(NS_SOCKETTRANSPORTSERVICE_CID);
 NS_DEFINE_NAMED_CID(NS_SERVERSOCKET_CID);
 NS_DEFINE_NAMED_CID(NS_SOCKETPROVIDERSERVICE_CID);
@@ -923,19 +923,19 @@ static const mozilla::Module::CIDEntry k
 #ifdef NECKO_PROTOCOL_viewsource
     { &kNS_VIEWSOURCEHANDLER_CID, false, NULL, nsViewSourceHandlerConstructor },
 #endif
 #ifdef NECKO_PROTOCOL_wyciwyg
     { &kNS_WYCIWYGPROTOCOLHANDLER_CID, false, NULL, nsWyciwygProtocolHandlerConstructor },
 #endif
 #ifdef NECKO_PROTOCOL_websocket
     { &kNS_WEBSOCKETPROTOCOLHANDLER_CID, false, NULL,
-      mozilla::net::nsWebSocketHandlerConstructor },
+      mozilla::net::WebSocketChannelConstructor },
     { &kNS_WEBSOCKETSSLPROTOCOLHANDLER_CID, false, NULL,
-      mozilla::net::nsWebSocketSSLHandlerConstructor },
+      mozilla::net::WebSocketSSLChannelConstructor },
 #endif
 #if defined(XP_WIN)
     { &kNS_NETWORK_LINK_SERVICE_CID, false, NULL, nsNotifyAddrListenerConstructor },
 #elif defined(MOZ_WIDGET_COCOA)
     { &kNS_NETWORK_LINK_SERVICE_CID, false, NULL, nsNetworkLinkServiceConstructor },
 #elif defined(MOZ_ENABLE_LIBCONIC)
     { &kNS_NETWORK_LINK_SERVICE_CID, false, NULL, nsMaemoNetworkLinkServiceConstructor },
 #elif defined(MOZ_ENABLE_QTNETWORK)
diff --git a/netwerk/protocol/websocket/BaseWebSocketChannel.cpp b/netwerk/protocol/websocket/BaseWebSocketChannel.cpp
--- a/netwerk/protocol/websocket/BaseWebSocketChannel.cpp
+++ b/netwerk/protocol/websocket/BaseWebSocketChannel.cpp
@@ -34,17 +34,16 @@
  * and other provisions required by the GPL or the LGPL. If you do not delete
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
 #include "WebSocketLog.h"
 #include "BaseWebSocketChannel.h"
-#include "nsWebSocketHandler.h"
 #include "nsILoadGroup.h"
 #include "nsIInterfaceRequestor.h"
 #include "nsIURI.h"
 #include "nsAutoPtr.h"
 #include "nsStandardURL.h"
 
 #if defined(PR_LOGGING)
 PRLogModuleInfo *webSocketLog = nsnull;
@@ -58,17 +57,17 @@ BaseWebSocketChannel::BaseWebSocketChann
 {
 #if defined(PR_LOGGING)
   if (!webSocketLog)
     webSocketLog = PR_NewLogModule("nsWebSocket");
 #endif
 }
 
 //-----------------------------------------------------------------------------
-// BaseWebSocketChannel::nsIWebSocketProtocol
+// BaseWebSocketChannel::nsIWebSocketChannel
 //-----------------------------------------------------------------------------
 
 NS_IMETHODIMP
 BaseWebSocketChannel::GetOriginalURI(nsIURI **aOriginalURI)
 {
   LOG(("BaseWebSocketChannel::GetOriginalURI() %p\n", this));
 
   if (!mOriginalURI)
@@ -144,52 +143,52 @@ BaseWebSocketChannel::SetProtocol(const 
 //-----------------------------------------------------------------------------
 // BaseWebSocketChannel::nsIProtocolHandler
 //-----------------------------------------------------------------------------
 
 
 NS_IMETHODIMP
 BaseWebSocketChannel::GetScheme(nsACString &aScheme)
 {
-  LOG(("BaseWebSocketHandler::GetScheme() %p\n", this));
+  LOG(("BaseWebSocketChannel::GetScheme() %p\n", this));
 
   if (mEncrypted)
     aScheme.AssignLiteral("wss");
   else
     aScheme.AssignLiteral("ws");
   return NS_OK;
 }
 
 NS_IMETHODIMP
 BaseWebSocketChannel::GetDefaultPort(PRInt32 *aDefaultPort)
 {
-  LOG(("BaseWebSocketHandler::GetDefaultPort() %p\n", this));
+  LOG(("BaseWebSocketChannel::GetDefaultPort() %p\n", this));
 
   if (mEncrypted)
     *aDefaultPort = kDefaultWSSPort;
   else
     *aDefaultPort = kDefaultWSPort;
   return NS_OK;
 }
 
 NS_IMETHODIMP
 BaseWebSocketChannel::GetProtocolFlags(PRUint32 *aProtocolFlags)
 {
-  LOG(("BaseWebSocketHandler::GetProtocolFlags() %p\n", this));
+  LOG(("BaseWebSocketChannel::GetProtocolFlags() %p\n", this));
 
   *aProtocolFlags = URI_NORELATIVE | URI_NON_PERSISTABLE | ALLOWS_PROXY | 
       ALLOWS_PROXY_HTTP | URI_DOES_NOT_RETURN_DATA | URI_DANGEROUS_TO_LOAD;
   return NS_OK;
 }
 
 NS_IMETHODIMP
 BaseWebSocketChannel::NewURI(const nsACString & aSpec, const char *aOriginCharset,
                              nsIURI *aBaseURI, nsIURI **_retval NS_OUTPARAM)
 {
-  LOG(("BaseWebSocketHandler::NewURI() %p\n", this));
+  LOG(("BaseWebSocketChannel::NewURI() %p\n", this));
 
   PRInt32 port;
   nsresult rv = GetDefaultPort(&port);
   if (NS_FAILED(rv))
     return rv;
 
   nsRefPtr<nsStandardURL> url = new nsStandardURL();
   rv = url->Init(nsIStandardURL::URLTYPE_AUTHORITY, port, aSpec,
@@ -198,25 +197,25 @@ BaseWebSocketChannel::NewURI(const nsACS
     return rv;
   NS_ADDREF(*_retval = url);
   return NS_OK;
 }
 
 NS_IMETHODIMP
 BaseWebSocketChannel::NewChannel(nsIURI *aURI, nsIChannel **_retval NS_OUTPARAM)
 {
-  LOG(("BaseWebSocketHandler::NewChannel() %p\n", this));
+  LOG(("BaseWebSocketChannel::NewChannel() %p\n", this));
   return NS_ERROR_NOT_IMPLEMENTED;
 }
 
 NS_IMETHODIMP
 BaseWebSocketChannel::AllowPort(PRInt32 port, const char *scheme,
                                 PRBool *_retval NS_OUTPARAM)
 {
-  LOG(("BaseWebSocketHandler::AllowPort() %p\n", this));
+  LOG(("BaseWebSocketChannel::AllowPort() %p\n", this));
 
   // do not override any blacklisted ports
   *_retval = PR_FALSE;
   return NS_OK;
 }
 
 } // namespace net
 } // namespace mozilla
diff --git a/netwerk/protocol/websocket/BaseWebSocketChannel.h b/netwerk/protocol/websocket/BaseWebSocketChannel.h
--- a/netwerk/protocol/websocket/BaseWebSocketChannel.h
+++ b/netwerk/protocol/websocket/BaseWebSocketChannel.h
@@ -35,40 +35,41 @@
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
 #ifndef mozilla_net_BaseWebSocketChannel_h
 #define mozilla_net_BaseWebSocketChannel_h
 
-#include "nsIWebSocketProtocol.h"
+#include "nsIWebSocketChannel.h"
+#include "nsIWebSocketListener.h"
 #include "nsIProtocolHandler.h"
 #include "nsCOMPtr.h"
 #include "nsString.h"
 
 namespace mozilla {
 namespace net {
 
 const static PRInt32 kDefaultWSPort     = 80;
 const static PRInt32 kDefaultWSSPort    = 443;
 
-class BaseWebSocketChannel : public nsIWebSocketProtocol,
+class BaseWebSocketChannel : public nsIWebSocketChannel,
                              public nsIProtocolHandler
 {
  public:
   BaseWebSocketChannel();
 
   NS_DECL_NSIPROTOCOLHANDLER
 
   NS_IMETHOD QueryInterface(const nsIID & uuid, void **result NS_OUTPARAM) = 0;
   NS_IMETHOD_(nsrefcnt ) AddRef(void) = 0;
   NS_IMETHOD_(nsrefcnt ) Release(void) = 0;
 
-  // Partial implementation of nsIWebSocketProtocol
+  // Partial implementation of nsIWebSocketChannel
   //
   NS_IMETHOD GetOriginalURI(nsIURI **aOriginalURI);
   NS_IMETHOD GetURI(nsIURI **aURI);
   NS_IMETHOD GetNotificationCallbacks(nsIInterfaceRequestor **aNotificationCallbacks);
   NS_IMETHOD SetNotificationCallbacks(nsIInterfaceRequestor *aNotificationCallbacks);
   NS_IMETHOD GetLoadGroup(nsILoadGroup **aLoadGroup);
   NS_IMETHOD SetLoadGroup(nsILoadGroup *aLoadGroup);
   NS_IMETHOD GetProtocol(nsACString &aProtocol);
diff --git a/netwerk/protocol/websocket/Makefile.in b/netwerk/protocol/websocket/Makefile.in
--- a/netwerk/protocol/websocket/Makefile.in
+++ b/netwerk/protocol/websocket/Makefile.in
@@ -47,28 +47,29 @@ LIBRARY_NAME   = nkwebsocket_s
 LIBXUL_LIBRARY = 1
 XPIDL_MODULE   = necko_websocket
 GRE_MODULE     = 1
 FORCE_STATIC_LIB = 1
 
 EXPORTS_NAMESPACES = mozilla/net
 
 XPIDLSRCS = \
-  nsIWebSocketProtocol.idl \
+  nsIWebSocketChannel.idl \
+  nsIWebSocketListener.idl \
   $(NULL)
 
 CPPSRCS = \
-  nsWebSocketHandler.cpp \
+  WebSocketChannel.cpp \
   WebSocketChannelParent.cpp \
   WebSocketChannelChild.cpp \
   BaseWebSocketChannel.cpp \
   $(NULL)
 
 EXPORTS_mozilla/net = \
-  nsWebSocketHandler.h \
+  WebSocketChannel.h \
   WebSocketChannelParent.h \
   WebSocketChannelChild.h \
   BaseWebSocketChannel.h \
   $(NULL)
 
 LOCAL_INCLUDES = \
   -I$(srcdir)/../../base/src \
   -I$(topsrcdir)/content/base/src \
diff --git a/netwerk/protocol/websocket/PWebSocket.ipdl b/netwerk/protocol/websocket/PWebSocket.ipdl
--- a/netwerk/protocol/websocket/PWebSocket.ipdl
+++ b/netwerk/protocol/websocket/PWebSocket.ipdl
@@ -48,17 +48,17 @@ using IPC::URI;
 namespace mozilla {
 namespace net {
 
 async protocol PWebSocket
 {
   manager PNecko;
 
 parent:
-  // Forwarded methods corresponding to methods on nsIWebSocketProtocolHandler
+  // Forwarded methods corresponding to methods on nsIWebSocketChannel
   AsyncOpen(URI aURI, nsCString aOrigin, nsCString aProtocol, bool aSecure);
   Close();
   SendMsg(nsCString aMsg);
   SendBinaryMsg(nsCString aMsg);
 
   DeleteSelf();
 
 child:
diff --git a/netwerk/protocol/websocket/nsWebSocketHandler.cpp b/netwerk/protocol/websocket/WebSocketChannel.cpp
rename from netwerk/protocol/websocket/nsWebSocketHandler.cpp
rename to netwerk/protocol/websocket/WebSocketChannel.cpp
--- a/netwerk/protocol/websocket/nsWebSocketHandler.cpp
+++ b/netwerk/protocol/websocket/WebSocketChannel.cpp
@@ -1,9 +1,10 @@
 /* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
+/* vim: set sw=2 ts=8 et tw=80 : */
 /* ***** BEGIN LICENSE BLOCK *****
  * Version: MPL 1.1/GPL 2.0/LGPL 2.1
  *
  * The contents of this file are subject to the Mozilla Public License Version
  * 1.1 (the "License"); you may not use this file except in compliance with
  * the License. You may obtain a copy of the License at
  * http://www.mozilla.org/MPL/
  *
@@ -33,17 +34,17 @@
  * decision by deleting the provisions above and replace them with the notice
  * and other provisions required by the GPL or the LGPL. If you do not delete
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
 #include "WebSocketLog.h"
-#include "nsWebSocketHandler.h"
+#include "WebSocketChannel.h"
 
 #include "nsISocketTransportService.h"
 #include "nsIURI.h"
 #include "nsIChannel.h"
 #include "nsICryptoHash.h"
 #include "nsIRunnable.h"
 #include "nsIPrefBranch.h"
 #include "nsIPrefService.h"
@@ -72,18 +73,18 @@
 #include "prbit.h"
 #include "zlib.h"
 
 extern PRThread *gSocketThread;
 
 namespace mozilla {
 namespace net {
 
-NS_IMPL_THREADSAFE_ISUPPORTS11(nsWebSocketHandler,
-                               nsIWebSocketProtocol,
+NS_IMPL_THREADSAFE_ISUPPORTS11(WebSocketChannel,
+                               nsIWebSocketChannel,
                                nsIHttpUpgradeListener,
                                nsIRequestObserver,
                                nsIStreamListener,
                                nsIProtocolHandler,
                                nsIInputStreamCallback,
                                nsIOutputStreamCallback,
                                nsITimerCallback,
                                nsIDNSListener,
@@ -110,2474 +111,2357 @@ NS_IMPL_THREADSAFE_ISUPPORTS11(nsWebSock
  *
  */
 
 // some helper classes
 
 class CallOnMessageAvailable : public nsIRunnable
 {
 public:
-    NS_DECL_ISUPPORTS
-        
-    CallOnMessageAvailable(nsIWebSocketListener *aListener,
-                           nsISupports          *aContext,
-                           nsCString            &aData,
-                           PRInt32               aLen)
-      : mListener(aListener),
-        mContext(aContext),
-        mData(aData),
-        mLen(aLen) {}
-    
-    NS_SCRIPTABLE NS_IMETHOD Run()
-    {
-        if (mLen < 0)
-            mListener->OnMessageAvailable(mContext, mData);
-        else
-            mListener->OnBinaryMessageAvailable(mContext, mData);
-        return NS_OK;
-    }
+  NS_DECL_ISUPPORTS
+
+  CallOnMessageAvailable(nsIWebSocketListener *aListener,
+                         nsISupports          *aContext,
+                         nsCString            &aData,
+                         PRInt32               aLen)
+    : mListener(aListener),
+      mContext(aContext),
+      mData(aData),
+      mLen(aLen) {}
+
+  NS_SCRIPTABLE NS_IMETHOD Run()
+  {
+    if (mLen < 0)
+      mListener->OnMessageAvailable(mContext, mData);
+    else
+      mListener->OnBinaryMessageAvailable(mContext, mData);
+    return NS_OK;
+  }
 
 private:
-    ~CallOnMessageAvailable() {}
+  ~CallOnMessageAvailable() {}
 
-    nsCOMPtr<nsIWebSocketListener>    mListener;
-    nsCOMPtr<nsISupports>             mContext;
-    nsCString                         mData;
-    PRInt32                           mLen;
+  nsCOMPtr<nsIWebSocketListener>    mListener;
+  nsCOMPtr<nsISupports>             mContext;
+  nsCString                         mData;
+  PRInt32                           mLen;
 };
 NS_IMPL_THREADSAFE_ISUPPORTS1(CallOnMessageAvailable, nsIRunnable)
 
 class CallOnStop : public nsIRunnable
 {
 public:
-    NS_DECL_ISUPPORTS
-        
-    CallOnStop(nsIWebSocketListener *aListener,
-               nsISupports          *aContext,
-               nsresult              aData)
+  NS_DECL_ISUPPORTS
+
+  CallOnStop(nsIWebSocketListener *aListener,
+             nsISupports          *aContext,
+             nsresult              aData)
     : mListener(aListener),
       mContext(aContext),
       mData(aData) {}
-    
-    NS_SCRIPTABLE NS_IMETHOD Run()
-    {
-        mListener->OnStop(mContext, mData);
-        return NS_OK;
-    }
+
+  NS_SCRIPTABLE NS_IMETHOD Run()
+  {
+    mListener->OnStop(mContext, mData);
+    return NS_OK;
+  }
 
 private:
-    ~CallOnStop() {}
+  ~CallOnStop() {}
 
-    nsCOMPtr<nsIWebSocketListener>    mListener;
-    nsCOMPtr<nsISupports>             mContext;
-    nsresult                          mData;
+  nsCOMPtr<nsIWebSocketListener>    mListener;
+  nsCOMPtr<nsISupports>             mContext;
+  nsresult                          mData;
 };
 NS_IMPL_THREADSAFE_ISUPPORTS1(CallOnStop, nsIRunnable)
 
 class CallOnServerClose : public nsIRunnable
 {
 public:
-    NS_DECL_ISUPPORTS
-        
-    CallOnServerClose(nsIWebSocketListener *aListener,
-                      nsISupports          *aContext)
+  NS_DECL_ISUPPORTS
+
+  CallOnServerClose(nsIWebSocketListener *aListener,
+                    nsISupports          *aContext)
     : mListener(aListener),
       mContext(aContext) {}
-    
-    NS_SCRIPTABLE NS_IMETHOD Run()
-    {
-        mListener->OnServerClose(mContext);
-        return NS_OK;
-    }
+
+  NS_SCRIPTABLE NS_IMETHOD Run()
+  {
+    mListener->OnServerClose(mContext);
+    return NS_OK;
+  }
 
 private:
-    ~CallOnServerClose() {}
+  ~CallOnServerClose() {}
 
-    nsCOMPtr<nsIWebSocketListener>    mListener;
-    nsCOMPtr<nsISupports>             mContext;
+  nsCOMPtr<nsIWebSocketListener>    mListener;
+  nsCOMPtr<nsISupports>             mContext;
 };
 NS_IMPL_THREADSAFE_ISUPPORTS1(CallOnServerClose, nsIRunnable)
 
 class CallAcknowledge : public nsIRunnable
 {
 public:
-    NS_DECL_ISUPPORTS
-        
-    CallAcknowledge(nsIWebSocketListener *aListener,
-                    nsISupports          *aContext,
-                    PRUint32              aSize)
+  NS_DECL_ISUPPORTS
+
+  CallAcknowledge(nsIWebSocketListener *aListener,
+                  nsISupports          *aContext,
+                  PRUint32              aSize)
     : mListener(aListener),
       mContext(aContext),
       mSize(aSize) {}
 
-    NS_SCRIPTABLE NS_IMETHOD Run()
-    {
-        LOG(("WebSocketHandler::CallAcknowledge Size %u\n", mSize));
-        mListener->OnAcknowledge(mContext, mSize);
-        return NS_OK;
-    }
-    
+  NS_SCRIPTABLE NS_IMETHOD Run()
+  {
+    LOG(("WebSocketChannel::CallAcknowledge: Size %u\n", mSize));
+    mListener->OnAcknowledge(mContext, mSize);
+    return NS_OK;
+  }
+
 private:
-    ~CallAcknowledge() {}
+  ~CallAcknowledge() {}
 
-    nsCOMPtr<nsIWebSocketListener>    mListener;
-    nsCOMPtr<nsISupports>             mContext;
-    PRUint32                          mSize;
+  nsCOMPtr<nsIWebSocketListener>    mListener;
+  nsCOMPtr<nsISupports>             mContext;
+  PRUint32                          mSize;
 };
 NS_IMPL_THREADSAFE_ISUPPORTS1(CallAcknowledge, nsIRunnable)
 
 class nsPostMessage : public nsIRunnable
 {
 public:
-    NS_DECL_ISUPPORTS
-        
-    nsPostMessage(nsWebSocketHandler *handler,
-                  nsCString          *aData,
-                  PRInt32             aDataLen)
-        : mHandler(handler),
-        mData(aData),
-        mDataLen(aDataLen) {}
-    
-    NS_SCRIPTABLE NS_IMETHOD Run()
-    {
-        if (mData)
-            mHandler->SendMsgInternal(mData, mDataLen);
-        return NS_OK;
-    }
+  NS_DECL_ISUPPORTS
+
+  nsPostMessage(WebSocketChannel *channel,
+                nsCString        *aData,
+                PRInt32           aDataLen)
+    : mChannel(channel),
+      mData(aData),
+      mDataLen(aDataLen) {}
+
+  NS_SCRIPTABLE NS_IMETHOD Run()
+  {
+    if (mData)
+      mChannel->SendMsgInternal(mData, mDataLen);
+    return NS_OK;
+  }
 
 private:
-    ~nsPostMessage() {}
-    
-    nsRefPtr<nsWebSocketHandler>    mHandler;
-    nsCString                      *mData;
-    PRInt32                         mDataLen;
+  ~nsPostMessage() {}
+
+  nsRefPtr<WebSocketChannel>    mChannel;
+  nsCString                    *mData;
+  PRInt32                       mDataLen;
 };
 NS_IMPL_THREADSAFE_ISUPPORTS1(nsPostMessage, nsIRunnable)
 
 
 // Section 5.1 requires that a client rate limit its connects to a single
 // TCP session in the CONNECTING state (i.e. anything before the 101 upgrade
 // complete response comes back and an open javascript event is created)
 
 class nsWSAdmissionManager
 {
 public:
-    nsWSAdmissionManager()
-        : mConnectedCount(0)
-    {
-        MOZ_COUNT_CTOR(nsWSAdmissionManager);
-    }
+  nsWSAdmissionManager() : mConnectedCount(0)
+  {
+    MOZ_COUNT_CTOR(nsWSAdmissionManager);
+  }
+
+  class nsOpenConn
+  {
+  public:
+    nsOpenConn(nsCString &addr, WebSocketChannel *channel)
+      : mAddress(addr), mChannel(channel) { MOZ_COUNT_CTOR(nsOpenConn); }
+    ~nsOpenConn() { MOZ_COUNT_DTOR(nsOpenConn); }
+
+    nsCString mAddress;
+    nsRefPtr<WebSocketChannel> mChannel;
+  };
 
-    class nsOpenConn
-    {
-    public:
-        nsOpenConn(nsCString &addr, nsWebSocketHandler *handler)
-            : mAddress(addr), mHandler(handler)
-        { MOZ_COUNT_CTOR(nsOpenConn); }
-        ~nsOpenConn() {MOZ_COUNT_DTOR(nsOpenConn); }
-        
-        nsCString mAddress;
-        nsRefPtr<nsWebSocketHandler> mHandler;
-    };
-    
-    ~nsWSAdmissionManager()
-    {
-        MOZ_COUNT_DTOR(nsWSAdmissionManager);
-        for (PRUint32 i = 0; i < mData.Length(); i++)
-            delete mData[i];
-    }
+  ~nsWSAdmissionManager()
+  {
+    MOZ_COUNT_DTOR(nsWSAdmissionManager);
+    for (PRUint32 i = 0; i < mData.Length(); i++)
+      delete mData[i];
+  }
+
+  PRBool ConditionallyConnect(nsCString &aStr, WebSocketChannel *ws)
+  {
+    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    PRBool ConditionallyConnect(nsCString &aStr, nsWebSocketHandler *ws)
-    {
-        NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+    // if aStr is not in mData then we return true, else false.
+    // in either case aStr is then added to mData - meaning
+    // there will be duplicates when this function has been
+    // called with the same parameter multiple times.
 
-        // if aStr is not in mData then we return true, else false.
-        // in either case aStr is then added to mData - meaning
-        // there will be duplicates when this function has been
-        // called with the same parameter multiple times.
+    // we could hash this, but the dataset is expected to be
+    // small
 
-        // we could hash this, but the dataset is expected to be
-        // small
-        
-        PRBool found = (IndexOf(aStr) >= 0);
-        nsOpenConn *newdata = new nsOpenConn(aStr, ws);
-        mData.AppendElement(newdata);
+    PRBool found = (IndexOf(aStr) >= 0);
+    nsOpenConn *newdata = new nsOpenConn(aStr, ws);
+    mData.AppendElement(newdata);
 
-        if (!found)
-            ws->BeginOpen();
-        return !found;
-    }
+    if (!found)
+      ws->BeginOpen();
+    return !found;
+  }
 
-    PRBool Complete(nsCString &aStr)
-    {
-        NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-        PRInt32 index = IndexOf(aStr);
-        NS_ABORT_IF_FALSE(index >= 0, "completed connection not in open list");
-        
-        nsOpenConn *olddata = mData[index];
-        mData.RemoveElementAt(index);
-        delete olddata;
-        
-        // are there more of the same address pending dispatch?
-        index = IndexOf(aStr);
-        if (index >= 0) {
-            (mData[index])->mHandler->BeginOpen();
-            return PR_TRUE;
-        }
-        return PR_FALSE;
+  PRBool Complete(nsCString &aStr)
+  {
+    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+    PRInt32 index = IndexOf(aStr);
+    NS_ABORT_IF_FALSE(index >= 0, "completed connection not in open list");
+
+    nsOpenConn *olddata = mData[index];
+    mData.RemoveElementAt(index);
+    delete olddata;
+
+    // are there more of the same address pending dispatch?
+    index = IndexOf(aStr);
+    if (index >= 0) {
+      (mData[index])->mChannel->BeginOpen();
+      return PR_TRUE;
     }
+    return PR_FALSE;
+  }
 
-    void IncrementConnectedCount()
-    {
-        PR_ATOMIC_INCREMENT(&mConnectedCount);
-    }
+  void IncrementConnectedCount()
+  {
+    PR_ATOMIC_INCREMENT(&mConnectedCount);
+  }
 
-    void DecrementConnectedCount()
-    {
-        PR_ATOMIC_DECREMENT(&mConnectedCount);
-    }
+  void DecrementConnectedCount()
+  {
+    PR_ATOMIC_DECREMENT(&mConnectedCount);
+  }
 
-    PRInt32 ConnectedCount()
-    {
-        return mConnectedCount;
-    }
-    
+  PRInt32 ConnectedCount()
+  {
+    return mConnectedCount;
+  }
+
 private:
-    nsTArray<nsOpenConn *> mData;
+  nsTArray<nsOpenConn *> mData;
 
-    PRInt32 IndexOf(nsCString &aStr)
-    {
-        for (PRUint32 i = 0; i < mData.Length(); i++)
-            if (aStr == (mData[i])->mAddress)
-                return i;
-        return -1;
-    }
-    
-    // ConnectedCount might be decremented from the main or the socket
-    // thread, so manage it with atomic counters
-    PRInt32 mConnectedCount;
+  PRInt32 IndexOf(nsCString &aStr)
+  {
+    for (PRUint32 i = 0; i < mData.Length(); i++)
+      if (aStr == (mData[i])->mAddress)
+        return i;
+    return -1;
+  }
+
+  // ConnectedCount might be decremented from the main or the socket
+  // thread, so manage it with atomic counters
+  PRInt32 mConnectedCount;
 };
 
 // similar to nsDeflateConverter except for the mandatory FLUSH calls
 // required by websocket and the absence of the deflate termination
 // block which is appropriate because it would create data bytes after
 // sending the websockets CLOSE message.
 
 class nsWSCompression
 {
 public:
   nsWSCompression(nsIStreamListener *aListener,
                   nsISupports *aContext)
-      : mActive(PR_FALSE),
-        mContext(aContext),
-        mListener(aListener)
-    {
-        MOZ_COUNT_CTOR(nsWSCompression);
+    : mActive(PR_FALSE),
+      mContext(aContext),
+      mListener(aListener)
+  {
+    MOZ_COUNT_CTOR(nsWSCompression);
+
+    mZlib.zalloc = allocator;
+    mZlib.zfree = destructor;
+    mZlib.opaque = Z_NULL;
+
+    // Initialize the compressor - these are all the normal zlib
+    // defaults except window size is set to -15 instead of +15.
+    // This is the zlib way of specifying raw RFC 1951 output instead
+    // of the zlib rfc 1950 format which has a 2 byte header and
+    // adler checksum as a trailer
+
+    nsresult rv;
+    mStream = do_CreateInstance(NS_STRINGINPUTSTREAM_CONTRACTID, &rv);
+    if (NS_SUCCEEDED(rv) && aContext && aListener &&
+      deflateInit2(&mZlib, Z_DEFAULT_COMPRESSION, Z_DEFLATED, -15, 8,
+                   Z_DEFAULT_STRATEGY) == Z_OK) {
+      mActive = PR_TRUE;
+    }
+  }
+
+  ~nsWSCompression()
+  {
+    MOZ_COUNT_DTOR(nsWSCompression);
 
-        mZlib.zalloc = allocator;
-        mZlib.zfree = destructor;
-        mZlib.opaque = Z_NULL;
-        
-        // Initialize the compressor - these are all the normal zlib
-        // defaults except window size is set to -15 instead of +15.
-        // This is the zlib way of specifying raw RFC 1951 output instead
-        // of the zlib rfc 1950 format which has a 2 byte header and
-        // adler checksum as a trailer
-        
-        nsresult rv;
-        mStream = do_CreateInstance(NS_STRINGINPUTSTREAM_CONTRACTID, &rv);
-        if (NS_SUCCEEDED(rv) && aContext && aListener &&
-            deflateInit2(&mZlib, Z_DEFAULT_COMPRESSION, Z_DEFLATED,
-                         -15, 8, Z_DEFAULT_STRATEGY) == Z_OK) {
-            mActive = PR_TRUE;
-        }
-    }
+    if (mActive)
+      deflateEnd(&mZlib);
+  }
+
+  PRBool Active()
+  {
+    return mActive;
+  }
 
-    ~nsWSCompression()
-    {
-        MOZ_COUNT_DTOR(nsWSCompression);
+  nsresult Deflate(PRUint8 *buf1, PRUint32 buf1Len,
+                   PRUint8 *buf2, PRUint32 buf2Len)
+  {
+    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
+                          "not socket thread");
+    NS_ABORT_IF_FALSE(mActive, "not active");
 
-        if (mActive)
-            deflateEnd(&mZlib);
-    }
+    mZlib.avail_out = kBufferLen;
+    mZlib.next_out = mBuffer;
+    mZlib.avail_in = buf1Len;
+    mZlib.next_in = buf1;
+
+    nsresult rv;
 
-    PRBool Active()
-    {
-        return mActive;
+    while (mZlib.avail_in > 0) {
+      deflate(&mZlib, (buf2Len > 0) ? Z_NO_FLUSH : Z_SYNC_FLUSH);
+      rv = PushData();
+      if (NS_FAILED(rv))
+        return rv;
+      mZlib.avail_out = kBufferLen;
+      mZlib.next_out = mBuffer;
     }
 
-    nsresult Deflate(PRUint8 *buf1, PRUint32 buf1Len,
-                     PRUint8 *buf2, PRUint32 buf2Len)
-    {
-        NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                          "not socket thread");
-        NS_ABORT_IF_FALSE(mActive, "not active");
-        
-        mZlib.avail_out = kBufferLen;
-        mZlib.next_out = mBuffer;
-        mZlib.avail_in = buf1Len;
-        mZlib.next_in = buf1;
-        
-        nsresult rv;
-        
-        while (mZlib.avail_in > 0) {
-            deflate(&mZlib, (buf2Len > 0) ? Z_NO_FLUSH : Z_SYNC_FLUSH);
-            rv = PushData();
-            if (NS_FAILED(rv))
-                return rv;
-            mZlib.avail_out = kBufferLen;
-            mZlib.next_out = mBuffer;
-        }
-        
-        mZlib.avail_in = buf2Len;
-        mZlib.next_in = buf2;
+    mZlib.avail_in = buf2Len;
+    mZlib.next_in = buf2;
 
-        while (mZlib.avail_in > 0) {
-            deflate(&mZlib, Z_SYNC_FLUSH);
-            rv = PushData();
-            if (NS_FAILED(rv))
-                return rv;
-            mZlib.avail_out = kBufferLen;
-            mZlib.next_out = mBuffer;
-        }
-        
-        return NS_OK;
-    }
-    
-private:
-    
-    // use zlib data types
-    static void *allocator(void *opaque, uInt items, uInt size)
-    {
-        return moz_xmalloc(items * size);
+    while (mZlib.avail_in > 0) {
+      deflate(&mZlib, Z_SYNC_FLUSH);
+      rv = PushData();
+      if (NS_FAILED(rv))
+        return rv;
+      mZlib.avail_out = kBufferLen;
+      mZlib.next_out = mBuffer;
     }
 
-    static void destructor(void *opaque, void *addr)
-    {
-        moz_free(addr);
-    }
+    return NS_OK;
+  }
+
+private:
+
+  // use zlib data types
+  static void *allocator(void *opaque, uInt items, uInt size)
+  {
+    return moz_xmalloc(items * size);
+  }
+
+  static void destructor(void *opaque, void *addr)
+  {
+    moz_free(addr);
+  }
 
-    nsresult PushData()
-    {
-        PRUint32 bytesToWrite = kBufferLen - mZlib.avail_out;
-        if (bytesToWrite > 0) {
-            mStream->ShareData(reinterpret_cast<char *>(mBuffer), bytesToWrite);
-            nsresult rv;
-            rv = mListener->OnDataAvailable(nsnull, mContext,
-                                            mStream, 0, bytesToWrite);
-            if (NS_FAILED(rv))
-                return rv;
-        }
-        return NS_OK;
+  nsresult PushData()
+  {
+    PRUint32 bytesToWrite = kBufferLen - mZlib.avail_out;
+    if (bytesToWrite > 0) {
+      mStream->ShareData(reinterpret_cast<char *>(mBuffer), bytesToWrite);
+      nsresult rv =
+        mListener->OnDataAvailable(nsnull, mContext, mStream, 0, bytesToWrite);
+      if (NS_FAILED(rv))
+        return rv;
     }
-
-    PRBool    mActive;
-    z_stream  mZlib;
-    nsCOMPtr<nsIStringInputStream>  mStream;
+    return NS_OK;
+  }
 
-    nsISupports *mContext;                        /* weak ref */
-    nsIStreamListener *mListener;                 /* weak ref */
-    
-    const static PRInt32 kBufferLen = 4096;
-    PRUint8   mBuffer[kBufferLen];
+  PRBool                          mActive;
+  z_stream                        mZlib;
+  nsCOMPtr<nsIStringInputStream>  mStream;
+
+  nsISupports                    *mContext;     /* weak ref */
+  nsIStreamListener              *mListener;    /* weak ref */
+
+  const static PRInt32            kBufferLen = 4096;
+  PRUint8                         mBuffer[kBufferLen];
 };
 
 static nsWSAdmissionManager *sWebSocketAdmissions = nsnull;
 
-// nsWebSocketHandler
+// WebSocketChannel
 
-nsWebSocketHandler::nsWebSocketHandler() :
-    mCloseTimeout(20000),
-    mOpenTimeout(20000),
-    mPingTimeout(0),
-    mPingResponseTimeout(10000),
-    mMaxConcurrentConnections(200),
-    mRecvdHttpOnStartRequest(0),
-    mRecvdHttpUpgradeTransport(0),
-    mRequestedClose(0),
-    mClientClosed(0),
-    mServerClosed(0),
-    mStopped(0),
-    mCalledOnStop(0),
-    mPingOutstanding(0),
-    mAllowCompression(1),
-    mAutoFollowRedirects(0),
-    mReleaseOnTransmit(0),
-    mTCPClosed(0),
-    mMaxMessageSize(16000000),
-    mStopOnClose(NS_OK),
-    mCloseCode(kCloseAbnormal),
-    mFragmentOpcode(0),
-    mFragmentAccumulator(0),
-    mBuffered(0),
-    mBufferSize(16384),
-    mCurrentOut(nsnull),
-    mCurrentOutSent(0),
-    mCompressor(nsnull),
-    mDynamicOutputSize(0),
-    mDynamicOutput(nsnull)
+WebSocketChannel::WebSocketChannel() :
+  mCloseTimeout(20000),
+  mOpenTimeout(20000),
+  mPingTimeout(0),
+  mPingResponseTimeout(10000),
+  mMaxConcurrentConnections(200),
+  mRecvdHttpOnStartRequest(0),
+  mRecvdHttpUpgradeTransport(0),
+  mRequestedClose(0),
+  mClientClosed(0),
+  mServerClosed(0),
+  mStopped(0),
+  mCalledOnStop(0),
+  mPingOutstanding(0),
+  mAllowCompression(1),
+  mAutoFollowRedirects(0),
+  mReleaseOnTransmit(0),
+  mTCPClosed(0),
+  mMaxMessageSize(16000000),
+  mStopOnClose(NS_OK),
+  mCloseCode(kCloseAbnormal),
+  mFragmentOpcode(0),
+  mFragmentAccumulator(0),
+  mBuffered(0),
+  mBufferSize(16384),
+  mCurrentOut(nsnull),
+  mCurrentOutSent(0),
+  mCompressor(nsnull),
+  mDynamicOutputSize(0),
+  mDynamicOutput(nsnull)
 {
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+
+  LOG(("WebSocketChannel::WebSocketChannel() %p\n", this));
 
-    LOG(("WebSocketHandler::nsWebSocketHandler() %p\n", this));
-    
-    if (!sWebSocketAdmissions)
-        sWebSocketAdmissions = new nsWSAdmissionManager();
+  if (!sWebSocketAdmissions)
+    sWebSocketAdmissions = new nsWSAdmissionManager();
 
-    mFramePtr = mBuffer = static_cast<PRUint8 *>(moz_xmalloc(mBufferSize));
+  mFramePtr = mBuffer = static_cast<PRUint8 *>(moz_xmalloc(mBufferSize));
 }
 
-nsWebSocketHandler::~nsWebSocketHandler()
+WebSocketChannel::~WebSocketChannel()
 {
-    LOG(("WebSocketHandler::~nsWebSocketHandler() %p\n", this));
+  LOG(("WebSocketChannel::~WebSocketChannel() %p\n", this));
+
+  // this stop is a nop if the normal connect/close is followed
+  mStopped = 1;
+  StopSession(NS_ERROR_UNEXPECTED);
 
-    // this stop is a nop if the normal connect/close is followed
-    mStopped = 1;
-    StopSession(NS_ERROR_UNEXPECTED);
-    
-    moz_free(mBuffer);
-    moz_free(mDynamicOutput);
-    delete mCompressor;
+  moz_free(mBuffer);
+  moz_free(mDynamicOutput);
+  delete mCompressor;
+  delete mCurrentOut;
+
+  while ((mCurrentOut = (OutboundMessage *) mOutgoingPingMessages.PopFront()))
+    delete mCurrentOut;
+  while ((mCurrentOut = (OutboundMessage *) mOutgoingPongMessages.PopFront()))
+    delete mCurrentOut;
+  while ((mCurrentOut = (OutboundMessage *) mOutgoingMessages.PopFront()))
     delete mCurrentOut;
 
-    while ((mCurrentOut = (OutboundMessage *) mOutgoingPingMessages.PopFront()))
-        delete mCurrentOut;
-    while ((mCurrentOut = (OutboundMessage *) mOutgoingPongMessages.PopFront()))
-        delete mCurrentOut;
-    while ((mCurrentOut = (OutboundMessage *) mOutgoingMessages.PopFront()))
-        delete mCurrentOut;
+  nsCOMPtr<nsIThread> mainThread;
+  nsIURI *forgettable;
+  NS_GetMainThread(getter_AddRefs(mainThread));
+
+  if (mURI) {
+    mURI.forget(&forgettable);
+    NS_ProxyRelease(mainThread, forgettable, PR_FALSE);
+  }
 
-    nsCOMPtr<nsIThread> mainThread;
-    nsIURI *forgettable;
-    NS_GetMainThread(getter_AddRefs(mainThread));
-    
-    if (mURI) {
-        mURI.forget(&forgettable);
-        NS_ProxyRelease(mainThread, forgettable, PR_FALSE);
-    }
-    
-    if (mOriginalURI) {
-        mOriginalURI.forget(&forgettable);
-        NS_ProxyRelease(mainThread, forgettable, PR_FALSE);
-    }
+  if (mOriginalURI) {
+    mOriginalURI.forget(&forgettable);
+    NS_ProxyRelease(mainThread, forgettable, PR_FALSE);
+  }
 
-    if (mListener) {
-        nsIWebSocketListener *forgettableListener;
-        mListener.forget(&forgettableListener);
-        NS_ProxyRelease(mainThread, forgettableListener, PR_FALSE);
-    }
+  if (mListener) {
+    nsIWebSocketListener *forgettableListener;
+    mListener.forget(&forgettableListener);
+    NS_ProxyRelease(mainThread, forgettableListener, PR_FALSE);
+  }
 
-    if (mContext) {
-        nsISupports *forgettableContext;
-        mContext.forget(&forgettableContext);
-        NS_ProxyRelease(mainThread, forgettableContext, PR_FALSE);
-    }
+  if (mContext) {
+    nsISupports *forgettableContext;
+    mContext.forget(&forgettableContext);
+    NS_ProxyRelease(mainThread, forgettableContext, PR_FALSE);
+  }
 }
 
 void
-nsWebSocketHandler::Shutdown()
+WebSocketChannel::Shutdown()
 {
-    delete sWebSocketAdmissions;
-    sWebSocketAdmissions = nsnull;
+  delete sWebSocketAdmissions;
+  sWebSocketAdmissions = nsnull;
 }
 
 nsresult
-nsWebSocketHandler::BeginOpen()
+WebSocketChannel::BeginOpen()
 {
-    LOG(("WebSocketHandler::BeginOpen() %p\n", this));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  LOG(("WebSocketChannel::BeginOpen() %p\n", this));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    nsresult rv;
+  nsresult rv;
 
-    if (mRedirectCallback) {
-        LOG(("WebSocketHandler::BeginOpen Resuming Redirect\n"));
-        rv = mRedirectCallback->OnRedirectVerifyCallback(NS_OK);
-        mRedirectCallback = nsnull;
-        return rv;
-    }
+  if (mRedirectCallback) {
+    LOG(("WebSocketChannel::BeginOpen: Resuming Redirect\n"));
+    rv = mRedirectCallback->OnRedirectVerifyCallback(NS_OK);
+    mRedirectCallback = nsnull;
+    return rv;
+  }
 
-    nsCOMPtr<nsIChannel> localChannel = do_QueryInterface(mChannel, &rv);
-    if (NS_FAILED(rv)) {
-        LOG(("WebSocketHandler::BeginOpen cannot async open\n"));
-        AbortSession(NS_ERROR_CONNECTION_REFUSED);
-        return rv;
-    }
+  nsCOMPtr<nsIChannel> localChannel = do_QueryInterface(mChannel, &rv);
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel::BeginOpen: cannot async open\n"));
+    AbortSession(NS_ERROR_CONNECTION_REFUSED);
+    return rv;
+  }
 
-    rv = localChannel->AsyncOpen(this, mHttpChannel);
-    if (NS_FAILED(rv)) {
-        LOG(("WebSocketHandler::BeginOpen cannot async open\n"));
-        AbortSession(NS_ERROR_CONNECTION_REFUSED);
-        return rv;
-    }
+  rv = localChannel->AsyncOpen(this, mHttpChannel);
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel::BeginOpen: cannot async open\n"));
+    AbortSession(NS_ERROR_CONNECTION_REFUSED);
+    return rv;
+  }
 
-    mOpenTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
-    if (NS_SUCCEEDED(rv))
-        mOpenTimer->InitWithCallback(this, mOpenTimeout,
-                                     nsITimer::TYPE_ONE_SHOT);
+  mOpenTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
+  if (NS_SUCCEEDED(rv))
+    mOpenTimer->InitWithCallback(this, mOpenTimeout, nsITimer::TYPE_ONE_SHOT);
 
-    return rv;
+  return rv;
 }
 
 PRBool
-nsWebSocketHandler::IsPersistentFramePtr()
+WebSocketChannel::IsPersistentFramePtr()
 {
-    return (mFramePtr >= mBuffer && mFramePtr < mBuffer + mBufferSize);
+  return (mFramePtr >= mBuffer && mFramePtr < mBuffer + mBufferSize);
 }
 
-// extends the internal buffer by count and returns the total
+// Extends the internal buffer by count and returns the total
 // amount of data available for read
 PRUint32
-nsWebSocketHandler::UpdateReadBuffer(PRUint8 *buffer, PRUint32 count)
+WebSocketChannel::UpdateReadBuffer(PRUint8 *buffer, PRUint32 count)
 {
-    LOG(("WebSocketHandler::UpdateReadBuffer() %p [%p %u]\n",
+  LOG(("WebSocketChannel::UpdateReadBuffer() %p [%p %u]\n",
          this, buffer, count));
 
-    if (!mBuffered)
-        mFramePtr = mBuffer;
-    
-    NS_ABORT_IF_FALSE(IsPersistentFramePtr(),
-                      "update read buffer bad mFramePtr");
+  if (!mBuffered)
+    mFramePtr = mBuffer;
+
+  NS_ABORT_IF_FALSE(IsPersistentFramePtr(), "update read buffer bad mFramePtr");
 
-    if (mBuffered + count <= mBufferSize) {
-        // append to existing buffer
-        LOG(("WebSocketHandler:: update read buffer absorbed %u\n", count));
-    }
-    else if (mBuffered + count - (mFramePtr - mBuffer) <= mBufferSize) {
-        // make room in existing buffer by shifting unused data to start
-        mBuffered -= (mFramePtr - mBuffer);
-        LOG(("WebSocketHandler:: update read buffer shifted %u\n",
-             mBuffered));
-        ::memmove(mBuffer, mFramePtr, mBuffered);
-        mFramePtr = mBuffer;
-    }
-    else {
-        // existing buffer is not sufficient, extend it
-        mBufferSize += count + 8192;
-        LOG(("WebSocketHandler:: update read buffer extended to %u\n",
-             mBufferSize));
-        PRUint8 *old = mBuffer;
-        mBuffer = (PRUint8 *)moz_xrealloc(mBuffer, mBufferSize);
-        mFramePtr = mBuffer + (mFramePtr - old);
-    }
-    
-    ::memcpy(mBuffer + mBuffered, buffer, count);
-    mBuffered += count;
-    
-    return mBuffered - (mFramePtr - mBuffer);
+  if (mBuffered + count <= mBufferSize) {
+    // append to existing buffer
+    LOG(("WebSocketChannel: update read buffer absorbed %u\n", count));
+  } else if (mBuffered + count - (mFramePtr - mBuffer) <= mBufferSize) {
+    // make room in existing buffer by shifting unused data to start
+    mBuffered -= (mFramePtr - mBuffer);
+    LOG(("WebSocketChannel: update read buffer shifted %u\n", mBuffered));
+    ::memmove(mBuffer, mFramePtr, mBuffered);
+    mFramePtr = mBuffer;
+  } else {
+    // existing buffer is not sufficient, extend it
+    mBufferSize += count + 8192;
+    LOG(("WebSocketChannel: update read buffer extended to %u\n", mBufferSize));
+    PRUint8 *old = mBuffer;
+    mBuffer = (PRUint8 *)moz_xrealloc(mBuffer, mBufferSize);
+    mFramePtr = mBuffer + (mFramePtr - old);
+  }
+
+  ::memcpy(mBuffer + mBuffered, buffer, count);
+  mBuffered += count;
+
+  return mBuffered - (mFramePtr - mBuffer);
 }
 
 nsresult
-nsWebSocketHandler::ProcessInput(PRUint8 *buffer, PRUint32 count)
+WebSocketChannel::ProcessInput(PRUint8 *buffer, PRUint32 count)
 {
-    LOG(("WebSocketHandler::ProcessInput %p [%d %d]\n",
-         this, count, mBuffered));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    
-    // reset the ping timer
-    if (mPingTimer) {
-        // The purpose of ping/pong is to actively probe the peer so that an
-        // unreachable peer is not mistaken for a period of idleness. This
-        // implementation accepts any application level read activity as a
-        // sign of life, it does not necessarily have to be a pong.
-        
-        mPingOutstanding = 0;
-        mPingTimer->SetDelay(mPingTimeout);
+  LOG(("WebSocketChannel::ProcessInput %p [%d %d]\n", this, count, mBuffered));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+
+  // reset the ping timer
+  if (mPingTimer) {
+    // The purpose of ping/pong is to actively probe the peer so that an
+    // unreachable peer is not mistaken for a period of idleness. This
+    // implementation accepts any application level read activity as a sign of
+    // life, it does not necessarily have to be a pong.
+    mPingOutstanding = 0;
+    mPingTimer->SetDelay(mPingTimeout);
+  }
+
+  PRUint32 avail;
+
+  if (!mBuffered) {
+    // Most of the time we can process right off the stack buffer without
+    // having to accumulate anything
+    mFramePtr = buffer;
+    avail = count;
+  } else {
+    avail = UpdateReadBuffer(buffer, count);
+  }
+
+  PRUint8 *payload;
+  PRUint32 totalAvail = avail;
+
+  while (avail >= 2) {
+    PRInt64 payloadLength = mFramePtr[1] & 0x7F;
+    PRUint8 finBit        = mFramePtr[0] & kFinalFragBit;
+    PRUint8 rsvBits       = mFramePtr[0] & 0x70;
+    PRUint8 maskBit       = mFramePtr[1] & kMaskBit;
+    PRUint8 opcode        = mFramePtr[0] & 0x0F;
+
+    PRUint32 framingLength = 2;
+    if (maskBit)
+      framingLength += 4;
+
+    if (payloadLength < 126) {
+      if (avail < framingLength)
+        break;
+    } else if (payloadLength == 126) {
+      // 16 bit length field
+      framingLength += 2;
+      if (avail < framingLength)
+        break;
+
+      payloadLength = mFramePtr[2] << 8 | mFramePtr[3];
+    } else {
+      // 64 bit length
+      framingLength += 8;
+      if (avail < framingLength)
+        break;
+
+      if (mFramePtr[2] & 0x80) {
+        // Section 4.2 says that the most significant bit MUST be
+        // 0. (i.e. this is really a 63 bit value)
+        LOG(("WebSocketChannel:: high bit of 64 bit length set"));
+        AbortSession(NS_ERROR_ILLEGAL_VALUE);
+        return NS_ERROR_ILLEGAL_VALUE;
+      }
+
+      // copy this in case it is unaligned
+      PRUint64 tempLen;
+      memcpy(&tempLen, mFramePtr + 2, 8);
+      payloadLength = PR_ntohll(tempLen);
     }
 
-    PRUint32 avail;
+    payload = mFramePtr + framingLength;
+    avail -= framingLength;
+
+    LOG(("WebSocketChannel::ProcessInput: payload %lld avail %lu\n",
+         payloadLength, avail));
 
-    if (!mBuffered) {
-        // most of the time we can process right off the stack buffer
-        // without having to accumulate anything
+    // we don't deal in > 31 bit websocket lengths.. and probably
+    // something considerably shorter (16MB by default)
+    if (payloadLength + mFragmentAccumulator > mMaxMessageSize) {
+      AbortSession(NS_ERROR_FILE_TOO_BIG);
+      return NS_ERROR_FILE_TOO_BIG;
+    }
+
+    if (avail < payloadLength)
+      break;
 
-        mFramePtr = buffer;
-        avail = count;
+    LOG(("WebSocketChannel::ProcessInput: Frame accumulated - opcode %d\n",
+         opcode));
+
+    if (maskBit) {
+      // This is unexpected - the server does not generally send masked
+      // frames to the client, but it is allowed
+      LOG(("WebSocketChannel:: Client RECEIVING masked frame."));
+
+      PRUint32 mask;
+      memcpy(&mask, payload - 4, 4);
+      mask = PR_ntohl(mask);
+      ApplyMask(mask, payload, payloadLength);
     }
-    else {
-        avail = UpdateReadBuffer(buffer, count);
+
+    // Control codes are required to have the fin bit set
+    if (!finBit && (opcode & kControlFrameMask)) {
+      LOG(("WebSocketChannel:: fragmented control frame code %d\n", opcode));
+      AbortSession(NS_ERROR_ILLEGAL_VALUE);
+      return NS_ERROR_ILLEGAL_VALUE;
     }
 
-    PRUint8 *payload;
-    PRUint32 totalAvail = avail;
+    if (rsvBits) {
+      LOG(("WebSocketChannel:: unexpected reserved bits %x\n", rsvBits));
+      AbortSession(NS_ERROR_ILLEGAL_VALUE);
+      return NS_ERROR_ILLEGAL_VALUE;
+    }
 
-    while (avail >= 2) {
+    if (!finBit || opcode == kContinuation) {
+      // This is part of a fragment response
 
-        PRInt64 payloadLength = mFramePtr[1] & 0x7F;
-        PRUint8 finBit        = mFramePtr[0] & kFinalFragBit;
-        PRUint8 rsvBits       = mFramePtr[0] & 0x70;
-        PRUint8 maskBit       = mFramePtr[1] & kMaskBit;
-        PRUint8 opcode        = mFramePtr[0] & 0x0F;
+      // Only the first frame has a non zero op code: Make sure we don't see a
+      // first frame while some old fragments are open
+      if ((mFragmentAccumulator != 0) && (opcode != kContinuation)) {
+        LOG(("WebSocketHeandler:: nested fragments\n"));
+        AbortSession(NS_ERROR_ILLEGAL_VALUE);
+        return NS_ERROR_ILLEGAL_VALUE;
+      }
+
+      LOG(("WebSocketChannel:: Accumulating Fragment %lld\n", payloadLength));
 
-        PRUint32 framingLength = 2; 
-        if (maskBit)
-            framingLength += 4;
+      if (opcode == kContinuation) {
+        // For frag > 1 move the data body back on top of the headers
+        // so we have contiguous stream of data
+        NS_ABORT_IF_FALSE(mFramePtr + framingLength == payload,
+                          "payload offset from frameptr wrong");
+        ::memmove(mFramePtr, payload, avail);
+        payload = mFramePtr;
+        if (mBuffered)
+          mBuffered -= framingLength;
+      } else {
+        mFragmentOpcode = opcode;
+      }
 
-        if (payloadLength < 126) {
-            if (avail < framingLength)
-                break;
-        }
-        else if (payloadLength == 126) {
-            // 16 bit length field
-            framingLength += 2;
-            if (avail < framingLength)
-                break;
+      if (finBit) {
+        LOG(("WebSocketChannel:: Finalizing Fragment\n"));
+        payload -= mFragmentAccumulator;
+        payloadLength += mFragmentAccumulator;
+        avail += mFragmentAccumulator;
+        mFragmentAccumulator = 0;
+        opcode = mFragmentOpcode;
+      } else {
+        opcode = kContinuation;
+        mFragmentAccumulator += payloadLength;
+      }
+    } else if (mFragmentAccumulator != 0 && !(opcode & kControlFrameMask)) {
+      // This frame is not part of a fragment sequence but we
+      // have an open fragment.. it must be a control code or else
+      // we have a problem
+      LOG(("WebSocketChannel:: illegal fragment sequence\n"));
+      AbortSession(NS_ERROR_ILLEGAL_VALUE);
+      return NS_ERROR_ILLEGAL_VALUE;
+    }
 
-            payloadLength = mFramePtr[2] << 8 | mFramePtr[3];
-        }
-        else {
-            // 64 bit length
-            framingLength += 8;
-            if (avail < framingLength)
-                break;
+    if (mServerClosed) {
+      LOG(("WebSocketChannel:: ignoring read frame code %d after close\n",
+                 opcode));
+      // nop
+    } else if (mStopped) {
+      LOG(("WebSocketChannel:: ignoring read frame code %d after completion\n",
+           opcode));
+    } else if (opcode == kText) {
+      LOG(("WebSocketChannel:: text frame received\n"));
+      if (mListener) {
+        nsCString utf8Data((const char *)payload, payloadLength);
 
-            if (mFramePtr[2] & 0x80) {
-                // Section 4.2 says that the most significant bit MUST be
-                // 0. (i.e. this is really a 63 bit value)
-                LOG(("WebSocketHandler:: high bit of 64 bit length set"));
-                AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                return NS_ERROR_ILLEGAL_VALUE;
-            }
-
-            // copy this in case it is unaligned
-            PRUint64 tempLen;
-            memcpy(&tempLen, mFramePtr + 2, 8);
-            payloadLength = PR_ntohll(tempLen);
+        // Section 8.1 says to replace received non utf-8 sequences
+        // (which are non-conformant to send) with u+fffd,
+        // but secteam feels that silently rewriting messages is
+        // inappropriate - so we will fail the connection instead.
+        if (!IsUTF8(utf8Data)) {
+          LOG(("WebSocketChannel:: text frame invalid utf-8\n"));
+          AbortSession(NS_ERROR_ILLEGAL_VALUE);
+          return NS_ERROR_ILLEGAL_VALUE;
         }
 
-        payload = mFramePtr + framingLength;
-        avail -= framingLength;
-        
-        LOG(("WebSocketHandler:: ProcessInput payload %lld avail %lu\n",
-             payloadLength, avail));
+        NS_DispatchToMainThread(new CallOnMessageAvailable(mListener, mContext,
+                                                           utf8Data, -1));
+      }
+    } else if (opcode & kControlFrameMask) {
+      // control frames
+      if (payloadLength > 125) {
+        LOG(("WebSocketChannel:: bad control frame code %d length %d\n",
+             opcode, payloadLength));
+        AbortSession(NS_ERROR_ILLEGAL_VALUE);
+        return NS_ERROR_ILLEGAL_VALUE;
+      }
 
-        // we don't deal in > 31 bit websocket lengths.. and probably
-        // something considerably shorter (16MB by default)
-        if (payloadLength + mFragmentAccumulator > mMaxMessageSize) {
-            AbortSession(NS_ERROR_FILE_TOO_BIG);
-            return NS_ERROR_FILE_TOO_BIG;
-        }
-        
-        if (avail < payloadLength)
-            break;
-
-        LOG(("WebSocketHandler::ProcessInput Frame accumulated - opcode %d\n",
-             opcode));
-
-        if (maskBit) {
-            // This is unexpected - the server does not generally send masked
-            // frames to the client, but it is allowed
-            LOG(("WebSocketHandler:: Client RECEIVING masked frame."));
+      if (opcode == kClose) {
+        LOG(("WebSocketChannel:: close received\n"));
+        mServerClosed = 1;
 
-            PRUint32 mask;
-            memcpy(&mask, payload - 4, 4);
-            mask = PR_ntohl(mask);
-            ApplyMask(mask, payload, payloadLength);
-        }
-        
-        // control codes are required to have the fin bit set
-        if (!finBit && (opcode & kControlFrameMask)) {
-            LOG(("WebSocketHandler:: fragmented control frame code %d\n",
-                 opcode));
-            AbortSession(NS_ERROR_ILLEGAL_VALUE);
-            return NS_ERROR_ILLEGAL_VALUE;
-        }
+        mCloseCode = kCloseNoStatus;
+        if (payloadLength >= 2) {
+          memcpy(&mCloseCode, payload, 2);
+          mCloseCode = PR_ntohs(mCloseCode);
+          LOG(("WebSocketChannel:: close recvd code %u\n", mCloseCode));
+          PRUint16 msglen = payloadLength - 2;
+          if (msglen > 0) {
+            nsCString utf8Data((const char *)payload + 2, msglen);
 
-        if (rsvBits) {
-            LOG(("WebSocketHandler:: unexpected reserved bits %x\n", rsvBits));
-            AbortSession(NS_ERROR_ILLEGAL_VALUE);
-            return NS_ERROR_ILLEGAL_VALUE;
-        }
-
-        if (!finBit || opcode == kContinuation) {
-            // This is part of a fragment response
-
-            // only the first frame has a non zero op code
-            // make sure we don't see a first frame while some old
-            // fragments are open
-            if ((mFragmentAccumulator != 0) && (opcode != kContinuation)) {
-                LOG(("WebSocketHeandler:: nested fragments\n"));
-                AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                return NS_ERROR_ILLEGAL_VALUE;
+            // section 8.1 says to replace received non utf-8 sequences
+            // (which are non-conformant to send) with u+fffd,
+            // but secteam feels that silently rewriting messages is
+            // inappropriate - so we will fail the connection instead.
+            if (!IsUTF8(utf8Data)) {
+              LOG(("WebSocketChannel:: close frame invalid utf-8\n"));
+              AbortSession(NS_ERROR_ILLEGAL_VALUE);
+              return NS_ERROR_ILLEGAL_VALUE;
             }
 
-            LOG(("WebSocketHandler:: Accumulating Fragment %lld\n",
-                 payloadLength));
-            
-            if (opcode == kContinuation) {
-                // for frag > 1 move the data body back on top of the headers
-                // so we have contiguous stream of data
-                NS_ABORT_IF_FALSE(mFramePtr + framingLength == payload,
-                                  "payload offset from frameptr wrong");
-                ::memmove (mFramePtr, payload, avail);
-                payload = mFramePtr;
-                if (mBuffered)
-                    mBuffered -= framingLength;
-            }
-            else {
-                mFragmentOpcode = opcode;
-            }
-            
-            if (finBit) {
-                LOG(("WebSocketHandler:: Finalizing Fragment\n"));
-                payload -= mFragmentAccumulator;
-                payloadLength += mFragmentAccumulator;
-                avail += mFragmentAccumulator;
-                mFragmentAccumulator = 0;
-                opcode = mFragmentOpcode;
-            } else {
-                opcode = kContinuation;
-                mFragmentAccumulator += payloadLength;
-            }
-        }
-        else if (mFragmentAccumulator != 0 && !(opcode & kControlFrameMask)) {
-            // this frame is not part of a fragment sequence but we
-            // have an open fragment.. it must be a control code or else
-            // we have a problem
-            LOG(("WebSocketHeandler:: illegal fragment sequence\n"));
-            AbortSession(NS_ERROR_ILLEGAL_VALUE);
-            return NS_ERROR_ILLEGAL_VALUE;
+            LOG(("WebSocketChannel:: close msg %s\n", utf8Data.get()));
+          }
         }
 
-        if (mServerClosed) {
-            LOG(("WebSocketHandler:: ignoring read frame code %d after close\n",
-                 opcode));
-            // nop
-        }
-        else if (mStopped) {
-            LOG(("WebSocketHandler:: "
-                 "ignoring read frame code %d after completion\n",
-                 opcode));
-        }
-        else if (opcode == kText) {
-            LOG(("WebSocketHandler:: text frame received\n"));
-            if (mListener) {
-                nsCString utf8Data((const char *)payload, payloadLength);
-
-                // section 8.1 says to replace received non utf-8 sequences
-                // (which are non-conformant to send) with u+fffd,
-                // but secteam feels that silently rewriting messages is
-                // inappropriate - so we will fail the connection instead.
-                if (!IsUTF8(utf8Data)) {
-                    LOG(("WebSocketHandler:: text frame invalid utf-8\n"));
-                    AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                    return NS_ERROR_ILLEGAL_VALUE;
-                }
-
-                nsCOMPtr<nsIRunnable> event =
-                    new CallOnMessageAvailable(mListener, mContext,
-                                               utf8Data, -1);
-                NS_DispatchToMainThread(event);
-            }
+        if (mCloseTimer) {
+          mCloseTimer->Cancel();
+          mCloseTimer = nsnull;
         }
-        else if (opcode & kControlFrameMask) {
-            // control frames
-            if (payloadLength > 125) {
-                LOG(("WebSocketHandler:: bad control frame code %d length %d\n",
-                     opcode, payloadLength));
-                AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                return NS_ERROR_ILLEGAL_VALUE;
-            }
-            
-            if (opcode == kClose) {
-                LOG(("WebSocketHandler:: close received\n"));
-                mServerClosed = 1;
-                
-                mCloseCode = kCloseNoStatus;
-                if (payloadLength >= 2) {
-                    memcpy(&mCloseCode, payload, 2);
-                    mCloseCode = PR_ntohs(mCloseCode);
-                    LOG(("WebSocketHandler:: close recvd code %u\n", mCloseCode));
-                    PRUint16 msglen = payloadLength - 2;
-                    if (msglen > 0) {
-                        nsCString utf8Data((const char *)payload + 2, msglen);
+        if (mListener)
+          NS_DispatchToMainThread(new CallOnServerClose(mListener, mContext));
 
-                        // section 8.1 says to replace received non utf-8 sequences
-                        // (which are non-conformant to send) with u+fffd,
-                        // but secteam feels that silently rewriting messages is
-                        // inappropriate - so we will fail the connection instead.
-                        if (!IsUTF8(utf8Data)) {
-                            LOG(("WebSocketHandler:: close frame invalid utf-8\n"));
-                            AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                            return NS_ERROR_ILLEGAL_VALUE;
-                        }
+        if (mClientClosed)
+          ReleaseSession();
+      } else if (opcode == kPing) {
+        LOG(("WebSocketChannel:: ping received\n"));
+        GeneratePong(payload, payloadLength);
+      } else {
+        // opcode kPong: the mere act of receiving the packet is all we need
+        // to do for the pong to trigger the activity timers
+        LOG(("WebSocketChannel:: pong received\n"));
+      }
 
-                        LOG(("WebSocketHandler:: close msg  %s\n",
-                             utf8Data.get()));
-                    }
-                }
-
-                if (mCloseTimer) {
-                    mCloseTimer->Cancel();
-                    mCloseTimer = nsnull;
-                }
-                if (mListener) {
-                    nsCOMPtr<nsIRunnable> event =
-                            new CallOnServerClose(mListener, mContext);
-                    NS_DispatchToMainThread(event);
-                }
-
-                if (mClientClosed)
-                    ReleaseSession();
-            }
-            else if (opcode == kPing) {
-                LOG(("WebSocketHandler:: ping received\n"));
-                GeneratePong(payload, payloadLength);
-            }
-            else {
-                // opcode kPong 
-                // The mere act of receiving the packet is all we need to
-                // do for the pong to trigger the activity timers
-                LOG(("WebSocketHandler:: pong received\n"));
-            }
-
-            if (mFragmentAccumulator) {
-                // we need to remove the control frame from the stream
-                // so we have a contiguous data buffer of reassembled fragments
-                LOG(("WebSocketHandler:: Removing Control From Read buffer\n"));
-                NS_ABORT_IF_FALSE(mFramePtr + framingLength == payload,
-                                  "payload offset from frameptr wrong");
-                ::memmove (mFramePtr, payload + payloadLength,
-                           avail - payloadLength);
-                payload = mFramePtr;
-                avail -= payloadLength;
-                payloadLength = 0;
-                if (mBuffered)
-                    mBuffered -= framingLength + payloadLength;
-            }
-        }
-        else if (opcode == kBinary) {
-            LOG(("WebSocketHandler:: binary frame received\n"));
-            if (mListener) {
-                nsCString binaryData((const char *)payload, payloadLength);
-                nsCOMPtr<nsIRunnable> event =
-                    new CallOnMessageAvailable(mListener, mContext,
-                                               binaryData, payloadLength);
-                NS_DispatchToMainThread(event);
-            }
-        }
-        else if (opcode != kContinuation) {
-            /* unknown opcode */
-            LOG(("WebSocketHandler:: unknown op code %d\n", opcode));
-            AbortSession(NS_ERROR_ILLEGAL_VALUE);
-            return NS_ERROR_ILLEGAL_VALUE;
-        }
-            
-        mFramePtr = payload + payloadLength;
+      if (mFragmentAccumulator) {
+        // Remove the control frame from the stream so we have a contiguous
+        // data buffer of reassembled fragments
+        LOG(("WebSocketChannel:: Removing Control From Read buffer\n"));
+        NS_ABORT_IF_FALSE(mFramePtr + framingLength == payload,
+                          "payload offset from frameptr wrong");
+        ::memmove(mFramePtr, payload + payloadLength, avail - payloadLength);
+        payload = mFramePtr;
         avail -= payloadLength;
-        totalAvail = avail;
+        payloadLength = 0;
+        if (mBuffered)
+          mBuffered -= framingLength + payloadLength;
+      }
+    } else if (opcode == kBinary) {
+      LOG(("WebSocketChannel:: binary frame received\n"));
+      if (mListener) {
+        nsCString binaryData((const char *)payload, payloadLength);
+        NS_DispatchToMainThread(new CallOnMessageAvailable(mListener, mContext,
+                                                           binaryData,
+                                                           payloadLength));
+      }
+    } else if (opcode != kContinuation) {
+      /* unknown opcode */
+      LOG(("WebSocketChannel:: unknown op code %d\n", opcode));
+      AbortSession(NS_ERROR_ILLEGAL_VALUE);
+      return NS_ERROR_ILLEGAL_VALUE;
     }
 
-    // Adjust the stateful buffer. If we were operating off the stack and
-    // now have a partial message then transition to the buffer, or if
-    // we were working off the buffer but no longer have any active state
-    // then transition to the stack
-    if (!IsPersistentFramePtr()) {
-        mBuffered = 0;
-        
-        if (mFragmentAccumulator) {
-            LOG(("WebSocketHandler:: Setup Buffer due to fragment"));
-            
-            UpdateReadBuffer(mFramePtr - mFragmentAccumulator,
-                             totalAvail + mFragmentAccumulator);
+    mFramePtr = payload + payloadLength;
+    avail -= payloadLength;
+    totalAvail = avail;
+  }
+
+  // Adjust the stateful buffer. If we were operating off the stack and
+  // now have a partial message then transition to the buffer, or if
+  // we were working off the buffer but no longer have any active state
+  // then transition to the stack
+  if (!IsPersistentFramePtr()) {
+    mBuffered = 0;
+
+    if (mFragmentAccumulator) {
+      LOG(("WebSocketChannel:: Setup Buffer due to fragment"));
 
-            // UpdateReadBuffer will reset the frameptr to the beginning
-            // of new saved state, so we need to skip past processed framgents
-            mFramePtr += mFragmentAccumulator;
-        }
-        else if (totalAvail) {
-            LOG(("WebSocketHandler:: Setup Buffer due to partial frame"));
-            UpdateReadBuffer(mFramePtr, totalAvail);
-        }
+      UpdateReadBuffer(mFramePtr - mFragmentAccumulator,
+                       totalAvail + mFragmentAccumulator);
+
+      // UpdateReadBuffer will reset the frameptr to the beginning
+      // of new saved state, so we need to skip past processed framgents
+      mFramePtr += mFragmentAccumulator;
+    } else if (totalAvail) {
+      LOG(("WebSocketChannel:: Setup Buffer due to partial frame"));
+      UpdateReadBuffer(mFramePtr, totalAvail);
     }
-    else if (!mFragmentAccumulator && !totalAvail) {
-        // If we were working off a saved buffer state and there is no
-        // partial frame or fragment in process, then revert to stack
-        // behavior
-        LOG(("WebSocketHandler:: Internal buffering not needed anymore"));
-        mBuffered = 0;
-    }
-    return NS_OK;
+  } else if (!mFragmentAccumulator && !totalAvail) {
+    // If we were working off a saved buffer state and there is no partial
+    // frame or fragment in process, then revert to stack behavior
+    LOG(("WebSocketChannel:: Internal buffering not needed anymore"));
+    mBuffered = 0;
+  }
+  return NS_OK;
 }
 
 void
-nsWebSocketHandler::ApplyMask(PRUint32 mask, PRUint8 *data, PRUint64 len)
+WebSocketChannel::ApplyMask(PRUint32 mask, PRUint8 *data, PRUint64 len)
 {
-    // Optimally we want to apply the mask 32 bits at a time,
-    // but the buffer might not be alligned. So we first deal with
-    // 0 to 3 bytes of preamble individually
+  // Optimally we want to apply the mask 32 bits at a time,
+  // but the buffer might not be alligned. So we first deal with
+  // 0 to 3 bytes of preamble individually
 
-    while (len && (reinterpret_cast<PRUptrdiff>(data) & 3)) {
-        *data ^= mask >> 24;
-        mask = PR_ROTATE_LEFT32(mask, 8);
-        data++;
-        len--;
-    }
-    
-    // perform mask on full words of data
+  while (len && (reinterpret_cast<PRUptrdiff>(data) & 3)) {
+    *data ^= mask >> 24;
+    mask = PR_ROTATE_LEFT32(mask, 8);
+    data++;
+    len--;
+  }
+
+  // perform mask on full words of data
 
-    PRUint32 *iData = (PRUint32 *) data;
-    PRUint32 *end = iData + (len / 4);
-    mask = PR_htonl(mask);
-    for (; iData < end; iData++)
-        *iData ^= mask;
-    mask = PR_ntohl(mask);
-    data = (PRUint8 *)iData;
-    len  = len % 4;
-    
-    // There maybe up to 3 trailing bytes that need to be dealt with
-    // individually 
-    
-    while (len) {
-        *data ^= mask >> 24;
-        mask = PR_ROTATE_LEFT32(mask, 8);
-        data++;
-        len--;
-    }
+  PRUint32 *iData = (PRUint32 *) data;
+  PRUint32 *end = iData + (len / 4);
+  mask = PR_htonl(mask);
+  for (; iData < end; iData++)
+    *iData ^= mask;
+  mask = PR_ntohl(mask);
+  data = (PRUint8 *)iData;
+  len  = len % 4;
+
+  // There maybe up to 3 trailing bytes that need to be dealt with
+  // individually 
+
+  while (len) {
+    *data ^= mask >> 24;
+    mask = PR_ROTATE_LEFT32(mask, 8);
+    data++;
+    len--;
+  }
 }
 
 void
-nsWebSocketHandler::GeneratePing()
+WebSocketChannel::GeneratePing()
 {
-    LOG(("WebSocketHandler::GeneratePing() %p\n", this));
+  LOG(("WebSocketChannel::GeneratePing() %p\n", this));
 
-    nsCString *buf = new nsCString();
-    buf->Assign("PING");
-    mOutgoingPingMessages.Push(new OutboundMessage(buf));
-    OnOutputStreamReady(mSocketOut);
+  nsCString *buf = new nsCString();
+  buf->Assign("PING");
+  mOutgoingPingMessages.Push(new OutboundMessage(buf));
+  OnOutputStreamReady(mSocketOut);
 }
 
 void
-nsWebSocketHandler::GeneratePong(PRUint8 *payload, PRUint32 len)
+WebSocketChannel::GeneratePong(PRUint8 *payload, PRUint32 len)
 {
-    LOG(("WebSocketHandler::GeneratePong() %p [%p %u]\n", this, payload, len));
+  LOG(("WebSocketChannel::GeneratePong() %p [%p %u]\n", this, payload, len));
 
-    nsCString *buf = new nsCString();
-    buf->SetLength(len);
-    if (buf->Length() < len) {
-        LOG(("WebSocketHandler::GeneratePong Allocation Failure\n"));
-        delete buf;
-        return;
-    }
-    
-    memcpy(buf->BeginWriting(), payload, len);
-    mOutgoingPongMessages.Push(new OutboundMessage(buf));
-    OnOutputStreamReady(mSocketOut);
+  nsCString *buf = new nsCString();
+  buf->SetLength(len);
+  if (buf->Length() < len) {
+    LOG(("WebSocketChannel::GeneratePong Allocation Failure\n"));
+    delete buf;
+    return;
+  }
+
+  memcpy(buf->BeginWriting(), payload, len);
+  mOutgoingPongMessages.Push(new OutboundMessage(buf));
+  OnOutputStreamReady(mSocketOut);
 }
 
 void
-nsWebSocketHandler::SendMsgInternal(nsCString *aMsg,
+WebSocketChannel::SendMsgInternal(nsCString *aMsg,
                                     PRInt32 aDataLen)
 {
-    LOG(("WebSocketHandler::SendMsgInternal %p [%p len=%d]\n",
-         this, aMsg, aDataLen));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    if (aMsg == kFinMessage)
-        mOutgoingMessages.Push(new OutboundMessage());
-    else if (aDataLen < 0)
-        mOutgoingMessages.Push(new OutboundMessage(aMsg));
-    else
-        mOutgoingMessages.Push(new OutboundMessage(aMsg, aDataLen));
-    OnOutputStreamReady(mSocketOut);
+  LOG(("WebSocketChannel::SendMsgInternal %p [%p len=%d]\n", this, aMsg,
+       aDataLen));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+  if (aMsg == kFinMessage) {
+    mOutgoingMessages.Push(new OutboundMessage());
+  } else if (aDataLen < 0) {
+    mOutgoingMessages.Push(new OutboundMessage(aMsg));
+  } else {
+    mOutgoingMessages.Push(new OutboundMessage(aMsg, aDataLen));
+  }
+  OnOutputStreamReady(mSocketOut);
 }
 
 PRUint16
-nsWebSocketHandler::ResultToCloseCode(nsresult resultCode)
+WebSocketChannel::ResultToCloseCode(nsresult resultCode)
 {
-    if (NS_SUCCEEDED(resultCode))
-        return kCloseNormal;
-    if (resultCode == NS_ERROR_FILE_TOO_BIG)
-        return kCloseTooLarge;
-    if (resultCode == NS_BASE_STREAM_CLOSED ||
-        resultCode == NS_ERROR_NET_TIMEOUT ||
-        resultCode == NS_ERROR_CONNECTION_REFUSED)
-        return kCloseAbnormal;
-    
-    return kCloseProtocolError;
+  if (NS_SUCCEEDED(resultCode))
+    return kCloseNormal;
+  if (resultCode == NS_ERROR_FILE_TOO_BIG)
+    return kCloseTooLarge;
+  if (resultCode == NS_BASE_STREAM_CLOSED ||
+      resultCode == NS_ERROR_NET_TIMEOUT ||
+      resultCode == NS_ERROR_CONNECTION_REFUSED) {
+    return kCloseAbnormal;
+  }
+
+  return kCloseProtocolError;
 }
 
 void
-nsWebSocketHandler::PrimeNewOutgoingMessage()
+WebSocketChannel::PrimeNewOutgoingMessage()
 {
-    LOG(("WebSocketHandler::PrimeNewOutgoingMessage() %p\n", this));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    NS_ABORT_IF_FALSE(!mCurrentOut, "Current message in progress");
+  LOG(("WebSocketChannel::PrimeNewOutgoingMessage() %p\n", this));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+  NS_ABORT_IF_FALSE(!mCurrentOut, "Current message in progress");
+
+  PRBool isPong = PR_FALSE;
+  PRBool isPing = PR_FALSE;
+
+  mCurrentOut = (OutboundMessage *)mOutgoingPongMessages.PopFront();
+  if (mCurrentOut) {
+    isPong = PR_TRUE;
+  } else {
+    mCurrentOut = (OutboundMessage *)mOutgoingPingMessages.PopFront();
+    if (mCurrentOut)
+      isPing = PR_TRUE;
+    else
+      mCurrentOut = (OutboundMessage *)mOutgoingMessages.PopFront();
+  }
+
+  if (!mCurrentOut)
+    return;
+  mCurrentOutSent = 0;
+  mHdrOut = mOutHeader;
+
+  PRUint8 *payload = nsnull;
+  if (mCurrentOut->IsControl() && !isPing && !isPong) {
+    // This is a demand to create a close message
+    if (mClientClosed) {
+      PrimeNewOutgoingMessage();
+      return;
+    }
+
+    LOG(("WebSocketChannel:: PrimeNewOutgoingMessage() found close request\n"));
+    mClientClosed = 1;
+    mOutHeader[0] = kFinalFragBit | kClose;
+    mOutHeader[1] = 0x02; // payload len = 2
+    mOutHeader[1] |= kMaskBit;
 
-    PRBool isPong = PR_FALSE;
-    PRBool isPing = PR_FALSE;
-    
-    mCurrentOut = (OutboundMessage *)mOutgoingPongMessages.PopFront();
-    if (mCurrentOut) {
-        isPong = PR_TRUE;
+    // payload is offset 6 including 4 for the mask
+    payload = mOutHeader + 6;
+
+    // The close reason code sits in the first 2 bytes of payload
+    *((PRUint16 *)payload) = PR_htons(ResultToCloseCode(mStopOnClose));
+
+    mHdrOutToSend = 8;
+    if (mServerClosed) {
+      /* bidi close complete */
+      mReleaseOnTransmit = 1;
+    } else if (NS_FAILED(mStopOnClose)) {
+      /* result of abort session - give up */
+      StopSession(mStopOnClose);
     } else {
-        mCurrentOut = (OutboundMessage *)mOutgoingPingMessages.PopFront();
-        if (mCurrentOut)
-            isPing = PR_TRUE;
-        else
-            mCurrentOut = (OutboundMessage *)mOutgoingMessages.PopFront();
+      /* wait for reciprocal close from server */
+      nsresult rv;
+      mCloseTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
+      if (NS_SUCCEEDED(rv)) {
+        mCloseTimer->InitWithCallback(this, mCloseTimeout,
+                                      nsITimer::TYPE_ONE_SHOT);
+      } else {
+        StopSession(rv);
+      }
+    }
+  } else {
+    if (isPong) {
+      LOG(("WebSocketChannel::PrimeNewOutgoingMessage() found pong request\n"));
+      mOutHeader[0] = kFinalFragBit | kPong;
+    } else if (isPing) {
+      LOG(("WebSocketChannel::PrimeNewOutgoingMessage() found ping request\n"));
+      mOutHeader[0] = kFinalFragBit | kPing;
+    } else if (mCurrentOut->BinaryLen() < 0) {
+      LOG(("WebSocketChannel::PrimeNewOutgoingMessage() "
+           "found queued text message len %d\n", mCurrentOut->Length()));
+      mOutHeader[0] = kFinalFragBit | kText;
+    } else {
+      LOG(("WebSocketChannel::PrimeNewOutgoingMessage() "
+           "found queued binary message len %d\n", mCurrentOut->Length()));
+      mOutHeader[0] = kFinalFragBit | kBinary;
     }
 
-    if (!mCurrentOut)
-        return;
-    mCurrentOutSent = 0;
-    mHdrOut = mOutHeader;
-
-    PRUint8 *payload = nsnull;
-    if (mCurrentOut->IsControl() && !isPing && !isPong) {
-        // This is a demand to create a close message
-        if (mClientClosed) {
-            PrimeNewOutgoingMessage();
-            return;
-        }
-            
-        LOG(("WebSocketHandler:: PrimeNewOutgoingMessage() "
-             "found close request\n"));
-        mClientClosed = 1;
-        mOutHeader[0] = kFinalFragBit | kClose;
-        mOutHeader[1] = 0x02; // payload len = 2
-        mOutHeader[1] |= kMaskBit;
-
-        // payload is offset 6 including 4 for the mask
-        payload = mOutHeader + 6;
-        
-        // The close reason code sits in the first 2 bytes of payload
-        *((PRUint16 *)payload) = PR_htons(ResultToCloseCode(mStopOnClose));
+    if (mCurrentOut->Length() < 126) {
+      mOutHeader[1] = mCurrentOut->Length() | kMaskBit;
+      mHdrOutToSend = 6;
+    } else if (mCurrentOut->Length() < 0xffff) {
+      mOutHeader[1] = 126 | kMaskBit;
+      ((PRUint16 *)mOutHeader)[1] =
+        PR_htons(mCurrentOut->Length());
+      mHdrOutToSend = 8;
+    } else {
+      mOutHeader[1] = 127 | kMaskBit;
+      PRUint64 tempLen = mCurrentOut->Length();
+      tempLen = PR_htonll(tempLen);
+      memcpy(mOutHeader + 2, &tempLen, 8);
+      mHdrOutToSend = 14;
+    }
+    payload = mOutHeader + mHdrOutToSend;
+  }
 
-        mHdrOutToSend = 8;
-        if (mServerClosed) {
-            /* bidi close complete */
-            mReleaseOnTransmit = 1;
-        }
-        else if (NS_FAILED(mStopOnClose)) {
-            /* result of abort session - give up */
-            StopSession(mStopOnClose);
-        }
-        else {
-            /* wait for reciprocal close from server */
-            nsresult rv;
-            mCloseTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
-            if (NS_SUCCEEDED(rv)) {
-                mCloseTimer->InitWithCallback(this, mCloseTimeout,
-                                              nsITimer::TYPE_ONE_SHOT);
-            }
-            else {
-                StopSession(rv);
-            }
-        }
+  NS_ABORT_IF_FALSE(payload, "payload offset not found");
+
+  // Perfom the sending mask. never use a zero mask
+  PRUint32 mask;
+  do {
+    PRUint8 *buffer;
+    nsresult rv = mRandomGenerator->GenerateRandomBytes(4, &buffer);
+    if (NS_FAILED(rv)) {
+      LOG(("WebSocketChannel::PrimeNewOutgoingMessage(): "
+           "GenerateRandomBytes failure %x\n", rv));
+      StopSession(rv);
+      return;
     }
-    else {
-        if (isPong) {
-            LOG(("WebSocketHandler:: PrimeNewOutgoingMessage() "
-                 "found pong request\n"));
-            mOutHeader[0] = kFinalFragBit | kPong;
-        }
-        else if (isPing) {
-            LOG(("WebSocketHandler:: PrimeNewOutgoingMessage() "
-                 "found ping request\n"));
-            mOutHeader[0] = kFinalFragBit | kPing;
-        }
-        else if (mCurrentOut->BinaryLen() < 0) {
-            LOG(("WebSocketHandler:: PrimeNewOutgoing Message() "
-                 "found queued text message len %d\n",
-                 mCurrentOut->Length()));
-            mOutHeader[0] = kFinalFragBit | kText;
-        }
-        else
-        {
-            LOG(("WebSocketHandler:: PrimeNewOutgoing Message() "
-                 "found queued binary message len %d\n",
-                 mCurrentOut->Length()));
-            mOutHeader[0] = kFinalFragBit | kBinary;
-        }
+    mask = * reinterpret_cast<PRUint32 *>(buffer);
+    NS_Free(buffer);
+  } while (!mask);
+  *(((PRUint32 *)payload) - 1) = PR_htonl(mask);
+
+  LOG(("WebSocketChannel::PrimeNewOutgoingMessage() using mask %08x\n", mask));
 
-        if (mCurrentOut->Length() < 126) {
-            mOutHeader[1] = mCurrentOut->Length() | kMaskBit;
-            mHdrOutToSend = 6;
-        }
-        else if (mCurrentOut->Length() < 0xffff) {
-            mOutHeader[1] = 126 | kMaskBit;
-            ((PRUint16 *)mOutHeader)[1] =
-                PR_htons(mCurrentOut->Length());
-            mHdrOutToSend = 8;
-        }
-        else {
-            mOutHeader[1] = 127 | kMaskBit;
-            PRUint64 tempLen = mCurrentOut->Length();
-            tempLen = PR_htonll(tempLen);
-            memcpy(mOutHeader + 2, &tempLen, 8);
-            mHdrOutToSend = 14;
-        }
-        payload = mOutHeader + mHdrOutToSend;
-    }
-    
-    NS_ABORT_IF_FALSE(payload, "payload offset not found");
-    
-    // Perfom the sending mask. never use a zero mask
-    PRUint32 mask;
-    do {
-        PRUint8 *buffer;
-        nsresult rv = mRandomGenerator->GenerateRandomBytes(4, &buffer);
-        if (NS_FAILED(rv)) {
-            LOG(("WebSocketHandler:: PrimeNewOutgoingMessage() "
-                 "GenerateRandomBytes failure %x\n", rv));
-            StopSession(rv);
-            return;
-        }
-        mask = * reinterpret_cast<PRUint32 *>(buffer);
-        NS_Free(buffer);
-    } while (!mask);
-    *(((PRUint32 *)payload) - 1) = PR_htonl(mask);
+  // We don't mask the framing, but occasionally we stick a little payload
+  // data in the buffer used for the framing. Close frames are the current
+  // example. This data needs to be masked, but it is never more than a
+  // handful of bytes and might rotate the mask, so we can just do it locally.
+  // For real data frames we ship the bulk of the payload off to ApplyMask()
 
-    LOG(("WebSocketHandler:: PrimeNewOutgoingMessage() "
-         "using mask %08x\n", mask));
+  while (payload < (mOutHeader + mHdrOutToSend)) {
+    *payload ^= mask >> 24;
+    mask = PR_ROTATE_LEFT32(mask, 8);
+    payload++;
+  }
+
+  // Mask the real message payloads
+
+  ApplyMask(mask, mCurrentOut->BeginWriting(), mCurrentOut->Length());
 
-    // We don't mask the framing, but occasionally we stick a little payload
-    // data in the buffer used for the framing. Close frames are the
-    // current example. This data needs to be
-    // masked, but it is never more than a handful of bytes and might rotate
-    // the mask, so we can just do it locally. For real data frames we
-    // ship the bulk of the payload off to ApplyMask()
+  // for small frames, copy it all together for a contiguous write
+  if (mCurrentOut->Length() <= kCopyBreak) {
+    memcpy(mOutHeader + mHdrOutToSend, mCurrentOut->BeginWriting(),
+           mCurrentOut->Length());
+    mHdrOutToSend += mCurrentOut->Length();
+    mCurrentOutSent = mCurrentOut->Length();
+  }
 
-    while (payload < (mOutHeader + mHdrOutToSend)) {
-        *payload ^= mask >> 24;
-        mask = PR_ROTATE_LEFT32(mask, 8);
-        payload++;
-    }
-
-    // Mask the real message payloads
+  if (mCompressor) {
+    // assume a 1/3 reduction in size for sizing the buffer
+    // the buffer is used multiple times if necessary
+    PRUint32 currentHeaderSize = mHdrOutToSend;
+    mHdrOutToSend = 0;
 
-    ApplyMask(mask,
-              mCurrentOut->BeginWriting(),
-              mCurrentOut->Length());
-    
-    // for small frames, copy it all together for a contiguous write
-    if (mCurrentOut->Length() <= kCopyBreak) {
-        memcpy(mOutHeader + mHdrOutToSend,
-               mCurrentOut->BeginWriting(),
-               mCurrentOut->Length());
-        mHdrOutToSend += mCurrentOut->Length();
-        mCurrentOutSent = mCurrentOut->Length();
-    }
+    EnsureHdrOut(32 +
+                 (currentHeaderSize + mCurrentOut->Length() - mCurrentOutSent)
+                 / 2 * 3);
+    mCompressor->Deflate(mOutHeader, currentHeaderSize,
+                         mCurrentOut->BeginReading() + mCurrentOutSent,
+                         mCurrentOut->Length() - mCurrentOutSent);
 
-    if (mCompressor) {
-        // assume a 1/3 reduction in size for sizing the buffer
-        // the buffer is used multiple times if necessary
-        PRUint32 currentHeaderSize = mHdrOutToSend;
-        mHdrOutToSend = 0;
-        
-        EnsureHdrOut(32 +
-                     (currentHeaderSize +
-                      mCurrentOut->Length() - mCurrentOutSent) / 2 * 3);
-        mCompressor->
-            Deflate(mOutHeader, currentHeaderSize,
-                    mCurrentOut->BeginReading() + mCurrentOutSent,
-                    mCurrentOut->Length() - mCurrentOutSent);
-        
-        // all of the compressed data now resides in {mHdrOut, mHdrOutToSend}
-        // so do not send the body again
-        mCurrentOutSent = mCurrentOut->Length();
-    }
+    // All of the compressed data now resides in {mHdrOut, mHdrOutToSend}
+    // so do not send the body again
+    mCurrentOutSent = mCurrentOut->Length();
+  }
 
-    // now the transmitting begins - mHdrOutToSend bytes from mOutHeader
-    // and mCurrentOut->Length() bytes from mCurrentOut. The latter may
-    // be coaleseced into the former for small messages or as the result
-    // of the compression process, 
+  // Transmitting begins - mHdrOutToSend bytes from mOutHeader and
+  // mCurrentOut->Length() bytes from mCurrentOut. The latter may be
+  // coaleseced into the former for small messages or as the result of the
+  // compression process,
 }
 
 void
-nsWebSocketHandler::EnsureHdrOut(PRUint32 size)
+WebSocketChannel::EnsureHdrOut(PRUint32 size)
 {
-    LOG(("WebSocketHandler::EnsureHdrOut() %p [%d]\n", this, size));
+  LOG(("WebSocketChannel::EnsureHdrOut() %p [%d]\n", this, size));
 
-    if (mDynamicOutputSize < size) {
-        mDynamicOutputSize = size;
-        mDynamicOutput =
-            (PRUint8 *) moz_xrealloc(mDynamicOutput, mDynamicOutputSize);
-    }
-    
-    mHdrOut = mDynamicOutput;
+  if (mDynamicOutputSize < size) {
+    mDynamicOutputSize = size;
+    mDynamicOutput =
+      (PRUint8 *) moz_xrealloc(mDynamicOutput, mDynamicOutputSize);
+  }
+
+  mHdrOut = mDynamicOutput;
 }
 
 void
-nsWebSocketHandler::CleanupConnection()
+WebSocketChannel::CleanupConnection()
 {
-    LOG(("WebSocketHandler::CleanupConnection() %p", this));
+  LOG(("WebSocketChannel::CleanupConnection() %p", this));
 
-    if (mLingeringCloseTimer) {
-        mLingeringCloseTimer->Cancel();
-        mLingeringCloseTimer = nsnull;
-    }
+  if (mLingeringCloseTimer) {
+    mLingeringCloseTimer->Cancel();
+    mLingeringCloseTimer = nsnull;
+  }
 
-    if (mSocketIn) {
-        if (sWebSocketAdmissions)
-            sWebSocketAdmissions->DecrementConnectedCount();
-        mSocketIn->AsyncWait(nsnull, 0, 0, nsnull);
-        mSocketIn = nsnull;
-    }
-    
-    if (mSocketOut) {
-        mSocketOut->AsyncWait(nsnull, 0, 0, nsnull);
-        mSocketOut = nsnull;
-    }
-    
-    if (mTransport) {
-        mTransport->SetSecurityCallbacks(nsnull);
-        mTransport->SetEventSink(nsnull, nsnull);
-        mTransport->Close(NS_BASE_STREAM_CLOSED);
-        mTransport = nsnull;
-    }
+  if (mSocketIn) {
+    if (sWebSocketAdmissions)
+      sWebSocketAdmissions->DecrementConnectedCount();
+    mSocketIn->AsyncWait(nsnull, 0, 0, nsnull);
+    mSocketIn = nsnull;
+  }
+
+  if (mSocketOut) {
+    mSocketOut->AsyncWait(nsnull, 0, 0, nsnull);
+    mSocketOut = nsnull;
+  }
+
+  if (mTransport) {
+    mTransport->SetSecurityCallbacks(nsnull);
+    mTransport->SetEventSink(nsnull, nsnull);
+    mTransport->Close(NS_BASE_STREAM_CLOSED);
+    mTransport = nsnull;
+  }
 }
 
 void
-nsWebSocketHandler::StopSession(nsresult reason)
+WebSocketChannel::StopSession(nsresult reason)
 {
-    LOG(("WebSocketHandler::StopSession() %p [%x]\n", this, reason));
+  LOG(("WebSocketChannel::StopSession() %p [%x]\n", this, reason));
 
-    // normally this should be called on socket thread, but it is ok to call it
-    // from OnStartRequest before the socket thread machine has gotten underway
+  // normally this should be called on socket thread, but it is ok to call it
+  // from OnStartRequest before the socket thread machine has gotten underway
 
-    NS_ABORT_IF_FALSE(mStopped, "stopsession() has not transitioned "
-                      "through abort or close");
+  NS_ABORT_IF_FALSE(mStopped,
+                    "stopsession() has not transitioned through abort or close");
 
-    if (mCloseTimer) {
-        mCloseTimer->Cancel();
-        mCloseTimer = nsnull;
-    }
+  if (mCloseTimer) {
+    mCloseTimer->Cancel();
+    mCloseTimer = nsnull;
+  }
 
-    if (mOpenTimer) {
-        mOpenTimer->Cancel();
-        mOpenTimer = nsnull;
-    }
+  if (mOpenTimer) {
+    mOpenTimer->Cancel();
+    mOpenTimer = nsnull;
+  }
 
-    if (mPingTimer) {
-        mPingTimer->Cancel();
-        mPingTimer = nsnull;
-    }
+  if (mPingTimer) {
+    mPingTimer->Cancel();
+    mPingTimer = nsnull;
+  }
 
-    if (mSocketIn && !mTCPClosed) {
-        // drain, within reason, this socket. if we leave any data
-        // unconsumed (including the tcp fin) a RST will be generated
-        // The right thing to do here is shutdown(SHUT_WR) and then wait
-        // a little while to see if any data comes in.. but there is no
-        // reason to delay things for that when the websocket handshake
-        // is supposed to guarantee a quiet connection except for that fin.
+  if (mSocketIn && !mTCPClosed) {
+    // Drain, within reason, this socket. if we leave any data
+    // unconsumed (including the tcp fin) a RST will be generated
+    // The right thing to do here is shutdown(SHUT_WR) and then wait
+    // a little while to see if any data comes in.. but there is no
+    // reason to delay things for that when the websocket handshake
+    // is supposed to guarantee a quiet connection except for that fin.
 
-        char     buffer[512];
-        PRUint32 count = 0;
-        PRUint32 total = 0;
-        nsresult rv;
-        do {
-            total += count;
-            rv = mSocketIn->Read(buffer, 512, &count);
-            if (rv != NS_BASE_STREAM_WOULD_BLOCK &&
-                (NS_FAILED(rv) || count == 0))
-                mTCPClosed = PR_TRUE;
-        } while (NS_SUCCEEDED(rv) && count > 0 && total < 32000);
-    }
+    char     buffer[512];
+    PRUint32 count = 0;
+    PRUint32 total = 0;
+    nsresult rv;
+    do {
+      total += count;
+      rv = mSocketIn->Read(buffer, 512, &count);
+      if (rv != NS_BASE_STREAM_WOULD_BLOCK &&
+        (NS_FAILED(rv) || count == 0))
+        mTCPClosed = PR_TRUE;
+    } while (NS_SUCCEEDED(rv) && count > 0 && total < 32000);
+  }
 
-    if (!mTCPClosed && mTransport && sWebSocketAdmissions &&
-        sWebSocketAdmissions->ConnectedCount() < kLingeringCloseThreshold) {
+  if (!mTCPClosed && mTransport && sWebSocketAdmissions &&
+    sWebSocketAdmissions->ConnectedCount() < kLingeringCloseThreshold) {
 
-        // 7.1.1 says that the client SHOULD wait for the server to close
-        // the TCP connection. This is so we can reuse port numbers before
-        // 2 MSL expires, which is not really as much of a concern for us
-        // as the amount of state that might be accrued by keeping this
-        // handler object around waiting for the server. We handle the SHOULD
-        // by waiting a short time in the common case, but not waiting in
-        // the case of high concurrency.
-        // 
-        // Normally this will be taken care of in AbortSession() after mTCPClosed
-        // is set when the server close arrives without waiting for the timeout to
-        // expire.
+    // 7.1.1 says that the client SHOULD wait for the server to close the TCP
+    // connection. This is so we can reuse port numbers before 2 MSL expires,
+    // which is not really as much of a concern for us as the amount of state
+    // that might be accrued by keeping this channel object around waiting for
+    // the server. We handle the SHOULD by waiting a short time in the common
+    // case, but not waiting in the case of high concurrency.
+    //
+    // Normally this will be taken care of in AbortSession() after mTCPClosed
+    // is set when the server close arrives without waiting for the timeout to
+    // expire.
 
-        LOG(("nsWebSocketHandler::StopSession - Wait for Server TCP close"));
+    LOG(("WebSocketChannel::StopSession: Wait for Server TCP close"));
 
-        nsresult rv;
-        mLingeringCloseTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
-        if (NS_SUCCEEDED(rv))
-            mLingeringCloseTimer->InitWithCallback(this, kLingeringCloseTimeout,
-                                                   nsITimer::TYPE_ONE_SHOT);
-        else
-            CleanupConnection();
-    }
-    else {
-        CleanupConnection();
-    }
-
-    if (mDNSRequest) {
-        mDNSRequest->Cancel(NS_ERROR_UNEXPECTED);
-        mDNSRequest = nsnull;
-    }
+    nsresult rv;
+    mLingeringCloseTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
+    if (NS_SUCCEEDED(rv))
+      mLingeringCloseTimer->InitWithCallback(this, kLingeringCloseTimeout,
+                                             nsITimer::TYPE_ONE_SHOT);
+    else
+      CleanupConnection();
+  } else {
+    CleanupConnection();
+  }
 
-    mInflateReader = nsnull;
-    mInflateStream = nsnull;
-    
-    delete mCompressor;
-    mCompressor = nsnull;
+  if (mDNSRequest) {
+    mDNSRequest->Cancel(NS_ERROR_UNEXPECTED);
+    mDNSRequest = nsnull;
+  }
+
+  mInflateReader = nsnull;
+  mInflateStream = nsnull;
 
-    if (!mCalledOnStop) {
-        mCalledOnStop = 1;
-        if (mListener) {
-            nsCOMPtr<nsIRunnable> event =
-                    new CallOnStop(mListener, mContext, reason);
-            NS_DispatchToMainThread(event);
-        }
-    }
+  delete mCompressor;
+  mCompressor = nsnull;
 
-    return;
+  if (!mCalledOnStop) {
+    mCalledOnStop = 1;
+    if (mListener)
+      NS_DispatchToMainThread(new CallOnStop(mListener, mContext, reason));
+  }
+
+  return;
 }
 
 void
-nsWebSocketHandler::AbortSession(nsresult reason)
+WebSocketChannel::AbortSession(nsresult reason)
 {
-    LOG(("WebSocketHandler::AbortSession() %p [reason %x] stopped = %d\n",
-         this, reason, mStopped));
+  LOG(("WebSocketChannel::AbortSession() %p [reason %x] stopped = %d\n",
+       this, reason, mStopped));
 
-    // normally this should be called on socket thread, but it is ok to call it
-    // from the main thread before StartWebsocketData() has completed
+  // normally this should be called on socket thread, but it is ok to call it
+  // from the main thread before StartWebsocketData() has completed
 
-    // When we are failing we need to close the TCP connection immediately
-    // as per 7.1.1
-    mTCPClosed = PR_TRUE;
+  // When we are failing we need to close the TCP connection immediately
+  // as per 7.1.1
+  mTCPClosed = PR_TRUE;
 
-    if (mLingeringCloseTimer) {
-        NS_ABORT_IF_FALSE(mStopped, "Lingering without Stop");
-        LOG(("Cleanup Connection based on TCP Close"));
-        CleanupConnection();
-        return;
-    }
-
-    if (mStopped)
-        return;
-    mStopped = 1;
+  if (mLingeringCloseTimer) {
+    NS_ABORT_IF_FALSE(mStopped, "Lingering without Stop");
+    LOG(("WebSocketChannel:: Cleanup connection based on TCP Close"));
+    CleanupConnection();
+    return;
+  }
 
-    if (mTransport && reason != NS_BASE_STREAM_CLOSED &&
-        !mRequestedClose && !mClientClosed && !mServerClosed) {
-        mRequestedClose = 1;
-        nsCOMPtr<nsIRunnable> event =
-            new nsPostMessage(this, kFinMessage, -1);
-        mSocketThread->Dispatch(event, nsIEventTarget::DISPATCH_NORMAL);
-        mStopOnClose = reason;
-    }
-    else {
-        StopSession(reason);
-    }
+  if (mStopped)
+    return;
+  mStopped = 1;
+
+  if (mTransport && reason != NS_BASE_STREAM_CLOSED &&
+      !mRequestedClose && !mClientClosed && !mServerClosed) {
+    mRequestedClose = 1;
+    mSocketThread->Dispatch(new nsPostMessage(this, kFinMessage, -1),
+                            nsIEventTarget::DISPATCH_NORMAL);
+    mStopOnClose = reason;
+  } else {
+    StopSession(reason);
+  }
 }
 
 // ReleaseSession is called on orderly shutdown
 void
-nsWebSocketHandler::ReleaseSession()
+WebSocketChannel::ReleaseSession()
 {
-    LOG(("WebSocketHandler::ReleaseSession() %p stopped = %d\n",
-         this, mStopped));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    
-    if (mStopped)
-        return;
-    mStopped = 1;
-    StopSession(NS_OK);
+  LOG(("WebSocketChannel::ReleaseSession() %p stopped = %d\n",
+       this, mStopped));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+
+  if (mStopped)
+    return;
+  mStopped = 1;
+  StopSession(NS_OK);
 }
 
 nsresult
-nsWebSocketHandler::HandleExtensions()
+WebSocketChannel::HandleExtensions()
 {
-    LOG(("WebSocketHandler::HandleExtensions() %p\n", this));
+  LOG(("WebSocketChannel::HandleExtensions() %p\n", this));
 
-    nsresult rv;
-    nsCAutoString extensions;
+  nsresult rv;
+  nsCAutoString extensions;
 
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    rv = mHttpChannel->GetResponseHeader(
-        NS_LITERAL_CSTRING("Sec-WebSocket-Extensions"), extensions);
-    if (NS_SUCCEEDED(rv)) {
-        if (!extensions.IsEmpty()) {
-            if (!extensions.Equals(NS_LITERAL_CSTRING("deflate-stream"))) {
-                LOG(("WebSocketHandler::OnStartRequest "
-                     "HTTP Sec-WebSocket-Exensions negotiated "
-                     "unknown value %s\n",
-                     extensions.get()));
-                AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                return NS_ERROR_ILLEGAL_VALUE;
-            }
+  rv = mHttpChannel->GetResponseHeader(
+    NS_LITERAL_CSTRING("Sec-WebSocket-Extensions"), extensions);
+  if (NS_SUCCEEDED(rv)) {
+    if (!extensions.IsEmpty()) {
+      if (!extensions.Equals(NS_LITERAL_CSTRING("deflate-stream"))) {
+        LOG(("WebSocketChannel::OnStartRequest: "
+             "HTTP Sec-WebSocket-Exensions negotiated unknown value %s\n",
+             extensions.get()));
+        AbortSession(NS_ERROR_ILLEGAL_VALUE);
+        return NS_ERROR_ILLEGAL_VALUE;
+      }
+
+      if (!mAllowCompression) {
+        LOG(("WebSocketChannel::HandleExtensions: "
+             "Recvd Compression Extension that wasn't offered\n"));
+        AbortSession(NS_ERROR_ILLEGAL_VALUE);
+        return NS_ERROR_ILLEGAL_VALUE;
+      }
 
-            if (!mAllowCompression) {
-                LOG(("WebSocketHandler::HandleExtensions "
-                     "Recvd Compression Extension that wasn't offered\n"));
-                AbortSession(NS_ERROR_ILLEGAL_VALUE);
-                return NS_ERROR_ILLEGAL_VALUE;
-            }
-            
-            nsCOMPtr<nsIStreamConverterService> serv =
-                do_GetService(NS_STREAMCONVERTERSERVICE_CONTRACTID, &rv);
-            if (NS_FAILED(rv)) {
-                LOG(("WebSocketHandler:: Cannot find compression service\n"));
-                AbortSession(NS_ERROR_UNEXPECTED);
-                return NS_ERROR_UNEXPECTED;
-            }
-            
-            rv = serv->AsyncConvertData("deflate",
-                                        "uncompressed",
-                                        this,
-                                        nsnull,
-                                        getter_AddRefs(mInflateReader));
-            
-            if (NS_FAILED(rv)) {
-                LOG(("WebSocketHandler:: Cannot find inflate listener\n"));
-                AbortSession(NS_ERROR_UNEXPECTED);
-                return NS_ERROR_UNEXPECTED;
-            }
-            
-            mInflateStream =
-                do_CreateInstance(NS_STRINGINPUTSTREAM_CONTRACTID, &rv);
-            
-            if (NS_FAILED(rv)) {
-                LOG(("WebSocketHandler:: Cannot find inflate stream\n"));
-                AbortSession(NS_ERROR_UNEXPECTED);
-                return NS_ERROR_UNEXPECTED;
-            }
-            
-            mCompressor = new nsWSCompression(this, mSocketOut);
-            if (!mCompressor->Active()) {
-                LOG(("WebSocketHandler:: Cannot init deflate object\n"));
-                delete mCompressor;
-                mCompressor = nsnull;
-                AbortSession(NS_ERROR_UNEXPECTED);
-                return NS_ERROR_UNEXPECTED;
-            }
-        }
+      nsCOMPtr<nsIStreamConverterService> serv =
+        do_GetService(NS_STREAMCONVERTERSERVICE_CONTRACTID, &rv);
+      if (NS_FAILED(rv)) {
+        LOG(("WebSocketChannel:: Cannot find compression service\n"));
+        AbortSession(NS_ERROR_UNEXPECTED);
+        return NS_ERROR_UNEXPECTED;
+      }
+
+      rv = serv->AsyncConvertData("deflate", "uncompressed", this, nsnull,
+                                  getter_AddRefs(mInflateReader));
+
+      if (NS_FAILED(rv)) {
+        LOG(("WebSocketChannel:: Cannot find inflate listener\n"));
+        AbortSession(NS_ERROR_UNEXPECTED);
+        return NS_ERROR_UNEXPECTED;
+      }
+
+      mInflateStream = do_CreateInstance(NS_STRINGINPUTSTREAM_CONTRACTID, &rv);
+
+      if (NS_FAILED(rv)) {
+        LOG(("WebSocketChannel:: Cannot find inflate stream\n"));
+        AbortSession(NS_ERROR_UNEXPECTED);
+        return NS_ERROR_UNEXPECTED;
+      }
+
+      mCompressor = new nsWSCompression(this, mSocketOut);
+      if (!mCompressor->Active()) {
+        LOG(("WebSocketChannel:: Cannot init deflate object\n"));
+        delete mCompressor;
+        mCompressor = nsnull;
+        AbortSession(NS_ERROR_UNEXPECTED);
+        return NS_ERROR_UNEXPECTED;
+      }
     }
-    
-    return NS_OK;
+  }
+
+  return NS_OK;
 }
 
 nsresult
-nsWebSocketHandler::SetupRequest()
+WebSocketChannel::SetupRequest()
 {
-    LOG(("WebSocketHandler::SetupRequest() %p\n", this));
+  LOG(("WebSocketChannel::SetupRequest() %p\n", this));
 
-    nsresult rv;
-    
-    if (mLoadGroup) {
-        rv = mHttpChannel->SetLoadGroup(mLoadGroup);
-        NS_ENSURE_SUCCESS(rv, rv);
-    }
+  nsresult rv;
 
-    rv = mHttpChannel->SetLoadFlags(nsIRequest::LOAD_BACKGROUND |
-                                    nsIRequest::INHIBIT_CACHING |
-                                    nsIRequest::LOAD_BYPASS_CACHE);
+  if (mLoadGroup) {
+    rv = mHttpChannel->SetLoadGroup(mLoadGroup);
     NS_ENSURE_SUCCESS(rv, rv);
-    
-    // draft-ietf-hybi-thewebsocketprotocol-07 illustrates Upgrade: websocket
-    // in lower case, so we will go with that. It is technically case
-    // insensitive.
-    rv = mChannel->HTTPUpgrade(NS_LITERAL_CSTRING("websocket"), this);
-    NS_ENSURE_SUCCESS(rv, rv);
+  }
+
+  rv = mHttpChannel->SetLoadFlags(nsIRequest::LOAD_BACKGROUND |
+                                  nsIRequest::INHIBIT_CACHING |
+                                  nsIRequest::LOAD_BYPASS_CACHE);
+  NS_ENSURE_SUCCESS(rv, rv);
+
+  // draft-ietf-hybi-thewebsocketprotocol-07 illustrates Upgrade: websocket
+  // in lower case, so go with that. It is technically case insensitive.
+  rv = mChannel->HTTPUpgrade(NS_LITERAL_CSTRING("websocket"), this);
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    mHttpChannel->SetRequestHeader(
-        NS_LITERAL_CSTRING("Sec-WebSocket-Version"),
-        NS_LITERAL_CSTRING(SEC_WEBSOCKET_VERSION), PR_FALSE);
+  mHttpChannel->SetRequestHeader(
+    NS_LITERAL_CSTRING("Sec-WebSocket-Version"),
+    NS_LITERAL_CSTRING(SEC_WEBSOCKET_VERSION), PR_FALSE);
 
-    if (!mOrigin.IsEmpty())
-        mHttpChannel->SetRequestHeader(
-            NS_LITERAL_CSTRING("Sec-WebSocket-Origin"),
-            mOrigin, PR_FALSE);
+  if (!mOrigin.IsEmpty())
+    mHttpChannel->SetRequestHeader(NS_LITERAL_CSTRING("Sec-WebSocket-Origin"),
+                                   mOrigin, PR_FALSE);
 
-    if (!mProtocol.IsEmpty())
-        mHttpChannel->SetRequestHeader(
-            NS_LITERAL_CSTRING("Sec-WebSocket-Protocol"),
-            mProtocol, PR_TRUE);
+  if (!mProtocol.IsEmpty())
+    mHttpChannel->SetRequestHeader(NS_LITERAL_CSTRING("Sec-WebSocket-Protocol"),
+                                   mProtocol, PR_TRUE);
 
-    if (mAllowCompression)
-        mHttpChannel->SetRequestHeader(
-            NS_LITERAL_CSTRING("Sec-WebSocket-Extensions"),
-            NS_LITERAL_CSTRING("deflate-stream"), PR_FALSE);
+  if (mAllowCompression)
+    mHttpChannel->SetRequestHeader(NS_LITERAL_CSTRING("Sec-WebSocket-Extensions"),
+                                   NS_LITERAL_CSTRING("deflate-stream"),
+                                   PR_FALSE);
+
+  PRUint8      *secKey;
+  nsCAutoString secKeyString;
 
-    PRUint8      *secKey;
-    nsCAutoString secKeyString;
-    
-    rv = mRandomGenerator->GenerateRandomBytes(16, &secKey);
-    NS_ENSURE_SUCCESS(rv, rv);
-    char* b64 = PL_Base64Encode((const char *)secKey, 16, nsnull);
-    NS_Free(secKey);
-    if (!b64) return NS_ERROR_OUT_OF_MEMORY;
-    secKeyString.Assign(b64);
-    PR_Free(b64);
-    mHttpChannel->SetRequestHeader(
-        NS_LITERAL_CSTRING("Sec-WebSocket-Key"), secKeyString, PR_FALSE);
-    LOG(("WebSocketHandler::AsyncOpen() client key %s\n", secKeyString.get()));
+  rv = mRandomGenerator->GenerateRandomBytes(16, &secKey);
+  NS_ENSURE_SUCCESS(rv, rv);
+  char* b64 = PL_Base64Encode((const char *)secKey, 16, nsnull);
+  NS_Free(secKey);
+  if (!b64)
+    return NS_ERROR_OUT_OF_MEMORY;
+  secKeyString.Assign(b64);
+  PR_Free(b64);
+  mHttpChannel->SetRequestHeader(NS_LITERAL_CSTRING("Sec-WebSocket-Key"),
+                                 secKeyString, PR_FALSE);
+  LOG(("WebSocketChannel::AsyncOpen(): client key %s\n", secKeyString.get()));
 
-    // prepare the value we expect to see in
-    // the sec-websocket-accept response header
-    secKeyString.AppendLiteral("258EAFA5-E914-47DA-95CA-C5AB0DC85B11");
-    nsCOMPtr<nsICryptoHash> hasher =
-        do_CreateInstance(NS_CRYPTO_HASH_CONTRACTID, &rv);
-    NS_ENSURE_SUCCESS(rv, rv);
-    rv = hasher->Init(nsICryptoHash::SHA1);
-    NS_ENSURE_SUCCESS(rv, rv);
-    rv = hasher->Update((const PRUint8 *) secKeyString.BeginWriting(),
-                        secKeyString.Length());
-    NS_ENSURE_SUCCESS(rv, rv);
-    rv = hasher->Finish(PR_TRUE, mHashedSecret);
-    NS_ENSURE_SUCCESS(rv, rv);
-    LOG(("WebSocketHandler::AsyncOpen() expected server key %s\n",
-         mHashedSecret.get()));
-    
-    return NS_OK;
+  // prepare the value we expect to see in
+  // the sec-websocket-accept response header
+  secKeyString.AppendLiteral("258EAFA5-E914-47DA-95CA-C5AB0DC85B11");
+  nsCOMPtr<nsICryptoHash> hasher =
+    do_CreateInstance(NS_CRYPTO_HASH_CONTRACTID, &rv);
+  NS_ENSURE_SUCCESS(rv, rv);
+  rv = hasher->Init(nsICryptoHash::SHA1);
+  NS_ENSURE_SUCCESS(rv, rv);
+  rv = hasher->Update((const PRUint8 *) secKeyString.BeginWriting(),
+                      secKeyString.Length());
+  NS_ENSURE_SUCCESS(rv, rv);
+  rv = hasher->Finish(PR_TRUE, mHashedSecret);
+  NS_ENSURE_SUCCESS(rv, rv);
+  LOG(("WebSocketChannel::AsyncOpen(): expected server key %s\n",
+       mHashedSecret.get()));
+
+  return NS_OK;
 }
 
 nsresult
-nsWebSocketHandler::ApplyForAdmission()
+WebSocketChannel::ApplyForAdmission()
 {
-    LOG(("WebSocketHandler::ApplyForAdmission() %p\n", this));
+  LOG(("WebSocketChannel::ApplyForAdmission() %p\n", this));
 
-    // Websockets has a policy of 1 session at a time being allowed in the
-    // CONNECTING state per server IP address (not hostname)
+  // Websockets has a policy of 1 session at a time being allowed in the
+  // CONNECTING state per server IP address (not hostname)
+
+  nsresult rv;
+  nsCOMPtr<nsIDNSService> dns = do_GetService(NS_DNSSERVICE_CONTRACTID, &rv);
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    nsresult rv;
-    nsCOMPtr<nsIDNSService> dns = do_GetService(NS_DNSSERVICE_CONTRACTID, &rv);
-    NS_ENSURE_SUCCESS(rv, rv);
-    
-    nsCString hostName;
-    rv = mURI->GetHost(hostName);
-    NS_ENSURE_SUCCESS(rv, rv);
-    mAddress = hostName;
-    
-    // expect the callback in ::OnLookupComplete
-    LOG(("WebSocketHandler::AsyncOpen() checking for concurrent open\n"));
-    nsCOMPtr<nsIThread> mainThread;
-    NS_GetMainThread(getter_AddRefs(mainThread));
-    dns->AsyncResolve(hostName,
-                      0,
-                      this,
-                      mainThread,
-                      getter_AddRefs(mDNSRequest));
-    NS_ENSURE_SUCCESS(rv, rv);
+  nsCString hostName;
+  rv = mURI->GetHost(hostName);
+  NS_ENSURE_SUCCESS(rv, rv);
+  mAddress = hostName;
 
-    return NS_OK;
+  // expect the callback in ::OnLookupComplete
+  LOG(("WebSocketChannel::AsyncOpen(): checking for concurrent open\n"));
+  nsCOMPtr<nsIThread> mainThread;
+  NS_GetMainThread(getter_AddRefs(mainThread));
+  dns->AsyncResolve(hostName, 0, this, mainThread, getter_AddRefs(mDNSRequest));
+  NS_ENSURE_SUCCESS(rv, rv);
+
+  return NS_OK;
 }
 
 // Called after both OnStartRequest and OnTransportAvailable have
 // executed. This essentially ends the handshake and starts the websockets
 // protocol state machine.
 nsresult
-nsWebSocketHandler::StartWebsocketData()
+WebSocketChannel::StartWebsocketData()
 {
-    LOG(("WebSocketHandler::StartWebsocketData() %p", this));
+  LOG(("WebSocketChannel::StartWebsocketData() %p", this));
 
-    if (sWebSocketAdmissions &&
-        sWebSocketAdmissions->ConnectedCount() > mMaxConcurrentConnections) {
-        LOG(("nsWebSocketHandler max concurrency %d exceeded "
-             "in OnTransportAvailable()",
-             mMaxConcurrentConnections));
-        
-        AbortSession(NS_ERROR_SOCKET_CREATE_FAILED);
-        return NS_OK;
-    }
+  if (sWebSocketAdmissions &&
+    sWebSocketAdmissions->ConnectedCount() > mMaxConcurrentConnections) {
+    LOG(("WebSocketChannel max concurrency %d exceeded "
+         "in OnTransportAvailable()", mMaxConcurrentConnections));
+    AbortSession(NS_ERROR_SOCKET_CREATE_FAILED);
+    return NS_OK;
+  }
 
-    return mSocketIn->AsyncWait(this, 0, 0, mSocketThread);
+  return mSocketIn->AsyncWait(this, 0, 0, mSocketThread);
 }
 
 // nsIDNSListener
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnLookupComplete(nsICancelable *aRequest,
+WebSocketChannel::OnLookupComplete(nsICancelable *aRequest,
                                      nsIDNSRecord *aRecord,
                                      nsresult aStatus)
 {
-    LOG(("WebSocketHandler::OnLookupComplete() %p [%p %p %x]\n",
-         this, aRequest, aRecord, aStatus));
+  LOG(("WebSocketChannel::OnLookupComplete() %p [%p %p %x]\n",
+       this, aRequest, aRecord, aStatus));
 
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    NS_ABORT_IF_FALSE(aRequest == mDNSRequest, "wrong dns request");
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  NS_ABORT_IF_FALSE(aRequest == mDNSRequest, "wrong dns request");
 
-    mDNSRequest = nsnull;
+  mDNSRequest = nsnull;
 
-    // These failures are not fatal - we just use the hostname as the key
-    if (NS_FAILED(aStatus)) {
-        LOG(("WebSocketHandler::OnLookupComplete No DNS Response\n"));
-    }
-    else {
-        nsresult rv = aRecord->GetNextAddrAsString(mAddress);
-        if (NS_FAILED(rv))
-            LOG(("WebSocketHandler::OnLookupComplete Failed GetNextAddr\n"));
-    }
-    
-    if (sWebSocketAdmissions->ConditionallyConnect(mAddress, this)) {
-        LOG(("WebSocketHandler::OnLookupComplete Proceeding with Open\n"));
-    }
-    else {
-        LOG(("WebSocketHandler::OnLookupComplete Deferring Open\n"));
-    }
-    
-    return NS_OK;
+  // These failures are not fatal - we just use the hostname as the key
+  if (NS_FAILED(aStatus)) {
+    LOG(("WebSocketChannel::OnLookupComplete: No DNS Response\n"));
+  } else {
+    nsresult rv = aRecord->GetNextAddrAsString(mAddress);
+    if (NS_FAILED(rv))
+      LOG(("WebSocketChannel::OnLookupComplete: Failed GetNextAddr\n"));
+  }
+
+  if (sWebSocketAdmissions->ConditionallyConnect(mAddress, this)) {
+    LOG(("WebSocketChannel::OnLookupComplete: Proceeding with Open\n"));
+  } else {
+    LOG(("WebSocketChannel::OnLookupComplete: Deferring Open\n"));
+  }
+
+  return NS_OK;
 }
 
 // nsIInterfaceRequestor
 
 NS_IMETHODIMP
-nsWebSocketHandler::GetInterface(const nsIID & iid, void **result NS_OUTPARAM)
+WebSocketChannel::GetInterface(const nsIID & iid, void **result NS_OUTPARAM)
 {
-    LOG(("WebSocketHandler::GetInterface() %p\n", this));
+  LOG(("WebSocketChannel::GetInterface() %p\n", this));
 
-    if (iid.Equals(NS_GET_IID(nsIChannelEventSink)))
-        return QueryInterface(iid, result);
-    
-    if (mCallbacks)
-        return mCallbacks->GetInterface(iid, result);
+  if (iid.Equals(NS_GET_IID(nsIChannelEventSink)))
+    return QueryInterface(iid, result);
 
-    return NS_ERROR_FAILURE;
+  if (mCallbacks)
+    return mCallbacks->GetInterface(iid, result);
+
+  return NS_ERROR_FAILURE;
 }
 
 // nsIChannelEventSink
 
 NS_IMETHODIMP
-nsWebSocketHandler::AsyncOnChannelRedirect(
-    nsIChannel *oldChannel,
-    nsIChannel *newChannel,
-    PRUint32 flags,
-    nsIAsyncVerifyRedirectCallback *callback)
+WebSocketChannel::AsyncOnChannelRedirect(
+                    nsIChannel *oldChannel,
+                    nsIChannel *newChannel,
+                    PRUint32 flags,
+                    nsIAsyncVerifyRedirectCallback *callback)
 {
-    LOG(("WebSocketHandler::AsyncOnChannelRedirect() %p\n", this));
-    nsresult rv;
-    
-    nsCOMPtr<nsIURI> newuri;
-    rv = newChannel->GetURI(getter_AddRefs(newuri));
-    NS_ENSURE_SUCCESS(rv, rv);
+  LOG(("WebSocketChannel::AsyncOnChannelRedirect() %p\n", this));
+  nsresult rv;
+
+  nsCOMPtr<nsIURI> newuri;
+  rv = newChannel->GetURI(getter_AddRefs(newuri));
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    if (!mAutoFollowRedirects) {
-        nsCAutoString spec;
-        if (NS_SUCCEEDED(newuri->GetSpec(spec)))
-            LOG(("nsWebSocketHandler Redirect to %s denied by configuration\n",
-                 spec.get()));
-        callback->OnRedirectVerifyCallback(NS_ERROR_FAILURE);
-        return NS_OK;
-    }
+  if (!mAutoFollowRedirects) {
+    nsCAutoString spec;
+    if (NS_SUCCEEDED(newuri->GetSpec(spec)))
+      LOG(("WebSocketChannel: Redirect to %s denied by configuration\n",
+            spec.get()));
+    callback->OnRedirectVerifyCallback(NS_ERROR_FAILURE);
+    return NS_OK;
+  }
+
+  PRBool isHttps = PR_FALSE;
+  rv = newuri->SchemeIs("https", &isHttps);
+  NS_ENSURE_SUCCESS(rv, rv);
+
+  if (mEncrypted && !isHttps) {
+    nsCAutoString spec;
+    if (NS_SUCCEEDED(newuri->GetSpec(spec)))
+      LOG(("WebSocketChannel: Redirect to %s violates encryption rule\n",
+           spec.get()));
+    callback->OnRedirectVerifyCallback(NS_ERROR_FAILURE);
+    return NS_OK;
+  }
+
+  nsCOMPtr<nsIHttpChannel> newHttpChannel = do_QueryInterface(newChannel, &rv);
 
-    PRBool isHttps = PR_FALSE;
-    rv = newuri->SchemeIs("https", &isHttps);
-    NS_ENSURE_SUCCESS(rv, rv);
-    
-    if (mEncrypted && !isHttps) {
-        nsCAutoString spec;
-        if (NS_SUCCEEDED(newuri->GetSpec(spec)))
-            LOG(("nsWebSocketHandler Redirect to %s violates encryption rule\n",
-                 spec.get()));
-        callback->OnRedirectVerifyCallback(NS_ERROR_FAILURE);
-        return NS_OK;
-    }
-    
-    nsCOMPtr<nsIHttpChannel> newHttpChannel =
-        do_QueryInterface(newChannel, &rv);
-    
-    if (NS_FAILED(rv)) {
-        LOG(("nsWebSocketHandler Redirect could not QI to HTTP\n"));
-        callback->OnRedirectVerifyCallback(rv);
-        return NS_OK;
-    }
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel: Redirect could not QI to HTTP\n"));
+    callback->OnRedirectVerifyCallback(rv);
+    return NS_OK;
+  }
+
+  nsCOMPtr<nsIHttpChannelInternal> newUpgradeChannel =
+    do_QueryInterface(newChannel, &rv);
+
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel: Redirect could not QI to HTTP Upgrade\n"));
+    callback->OnRedirectVerifyCallback(rv);
+    return NS_OK;
+  }
+
+  // The redirect is likely OK
 
-    nsCOMPtr<nsIHttpChannelInternal> newUpgradeChannel =
-        do_QueryInterface(newChannel, &rv);
-    
-    if (NS_FAILED(rv)) {
-        LOG(("nsWebSocketHandler Redirect could not QI to HTTP Upgrade\n"));
-        callback->OnRedirectVerifyCallback(rv);
-        return NS_OK;
-    }
-    
-    // The redirect is likely OK
+  newChannel->SetNotificationCallbacks(this);
+  mURI = newuri;
+  mHttpChannel = newHttpChannel;
+  mChannel = newUpgradeChannel;
+  rv = SetupRequest();
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel: Redirect could not SetupRequest()\n"));
+    callback->OnRedirectVerifyCallback(rv);
+    return NS_OK;
+  }
 
-    newChannel->SetNotificationCallbacks(this);
-    mURI = newuri;
-    mHttpChannel = newHttpChannel;
-    mChannel = newUpgradeChannel;
-    rv = SetupRequest();
-    if (NS_FAILED(rv)) {
-        LOG(("nsWebSocketHandler Redirect could not SetupRequest()\n"));
-        callback->OnRedirectVerifyCallback(rv);
-        return NS_OK;
-    }
-    
-    // We cannot just tell the callback OK right now due to the 1 connect at
-    // a time policy. First we need to complete the old location and then
-    // start the lookup chain for the new location - once that is complete
-    // and we have been admitted, OnRedirectVerifyCallback(NS_OK) will be called
-    // out of BeginOpen()
+  // We cannot just tell the callback OK right now due to the 1 connect at a
+  // time policy. First we need to complete the old location and then start the
+  // lookup chain for the new location - once that is complete and we have been
+  // admitted, OnRedirectVerifyCallback(NS_OK) will be called out of BeginOpen()
+
+  sWebSocketAdmissions->Complete(mAddress);
+  mAddress.Truncate();
+  mRedirectCallback = callback;
 
-    sWebSocketAdmissions->Complete(mAddress);
-    mAddress.Truncate();
-    mRedirectCallback = callback;
+  rv = ApplyForAdmission();
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel: Redirect failed due to DNS failure\n"));
+    callback->OnRedirectVerifyCallback(rv);
+    mRedirectCallback = nsnull;
+  }
 
-    rv = ApplyForAdmission();
-    if (NS_FAILED(rv)) {
-        LOG(("nsWebSocketHandler Redirect failed due to DNS failure\n"));
-        callback->OnRedirectVerifyCallback(rv);
-        mRedirectCallback = nsnull;
-    }
-    
-    return NS_OK;
+  return NS_OK;
 }
 
 // nsITimerCallback
 
 NS_IMETHODIMP
-nsWebSocketHandler::Notify(nsITimer *timer)
+WebSocketChannel::Notify(nsITimer *timer)
 {
-    LOG(("WebSocketHandler::Notify() %p [%p]\n", this, timer));
+  LOG(("WebSocketChannel::Notify() %p [%p]\n", this, timer));
 
-    if (timer == mCloseTimer) {
-        NS_ABORT_IF_FALSE(mClientClosed, "Close Timeout without local close");
-        NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
+  if (timer == mCloseTimer) {
+    NS_ABORT_IF_FALSE(mClientClosed, "Close Timeout without local close");
+    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
                       "not socket thread");
 
-        mCloseTimer = nsnull;
-        if (mStopped || mServerClosed)                /* no longer relevant */
-            return NS_OK;
-    
-        LOG(("nsWebSocketHandler:: Expecting Server Close - Timed Out\n"));
-        AbortSession(NS_ERROR_NET_TIMEOUT);
-    }
-    else if (timer == mOpenTimer) {
-        NS_ABORT_IF_FALSE(!mRecvdHttpOnStartRequest,
-                          "Open Timer after open complete");
-        NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+    mCloseTimer = nsnull;
+    if (mStopped || mServerClosed)                /* no longer relevant */
+      return NS_OK;
 
-        mOpenTimer = nsnull;
-        LOG(("nsWebSocketHandler:: Connection Timed Out\n"));
-        if (mStopped || mServerClosed)                /* no longer relevant */
-            return NS_OK;
-    
-        AbortSession(NS_ERROR_NET_TIMEOUT);
-    }
-    else if (timer == mPingTimer) {
-        NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
+    LOG(("WebSocketChannel:: Expecting Server Close - Timed Out\n"));
+    AbortSession(NS_ERROR_NET_TIMEOUT);
+  } else if (timer == mOpenTimer) {
+    NS_ABORT_IF_FALSE(!mRecvdHttpOnStartRequest,
+                      "Open Timer after open complete");
+    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+
+    mOpenTimer = nsnull;
+    LOG(("WebSocketChannel:: Connection Timed Out\n"));
+    if (mStopped || mServerClosed)                /* no longer relevant */
+      return NS_OK;
+
+    AbortSession(NS_ERROR_NET_TIMEOUT);
+  } else if (timer == mPingTimer) {
+    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
                       "not socket thread");
 
-        if (mClientClosed || mServerClosed || mRequestedClose) {
-            // no point in worrying about ping now
-            mPingTimer = nsnull;
-            return NS_OK;
-        }
-
-        if (!mPingOutstanding) {
-            LOG(("nsWebSockethandler:: Generating Ping\n"));
-            mPingOutstanding = 1;
-            GeneratePing();
-            mPingTimer->InitWithCallback(this, mPingResponseTimeout,
-                                         nsITimer::TYPE_ONE_SHOT);
-        }
-        else {
-            LOG(("nsWebSockethandler:: Timed out Ping\n"));
-            mPingTimer = nsnull;
-            AbortSession(NS_ERROR_NET_TIMEOUT);
-        }
-    }
-    else if (timer == mLingeringCloseTimer) {
-        LOG(("nsWebSocketHandler:: Lingering Close Timer"));
-        CleanupConnection();
-    }
-    else {
-        NS_ABORT_IF_FALSE(0, "Unknown Timer");
+    if (mClientClosed || mServerClosed || mRequestedClose) {
+      // no point in worrying about ping now
+      mPingTimer = nsnull;
+      return NS_OK;
     }
 
-    return NS_OK;
+    if (!mPingOutstanding) {
+      LOG(("nsWebSocketChannel:: Generating Ping\n"));
+      mPingOutstanding = 1;
+      GeneratePing();
+      mPingTimer->InitWithCallback(this, mPingResponseTimeout,
+                                   nsITimer::TYPE_ONE_SHOT);
+    } else {
+      LOG(("nsWebSocketChannel:: Timed out Ping\n"));
+      mPingTimer = nsnull;
+      AbortSession(NS_ERROR_NET_TIMEOUT);
+    }
+  } else if (timer == mLingeringCloseTimer) {
+    LOG(("WebSocketChannel:: Lingering Close Timer"));
+    CleanupConnection();
+  } else {
+    NS_ABORT_IF_FALSE(0, "Unknown Timer");
+  }
+
+  return NS_OK;
 }
 
 
 NS_IMETHODIMP
-nsWebSocketHandler::GetSecurityInfo(nsISupports **aSecurityInfo)
+WebSocketChannel::GetSecurityInfo(nsISupports **aSecurityInfo)
 {
-    LOG(("WebSocketHandler::GetSecurityInfo() %p\n", this));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  LOG(("WebSocketChannel::GetSecurityInfo() %p\n", this));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    if (mTransport) {
-        if (NS_FAILED(mTransport->GetSecurityInfo(aSecurityInfo)))
-            *aSecurityInfo = nsnull;
-    }
-    return NS_OK;
+  if (mTransport) {
+    if (NS_FAILED(mTransport->GetSecurityInfo(aSecurityInfo)))
+      *aSecurityInfo = nsnull;
+  }
+  return NS_OK;
 }
 
 
 NS_IMETHODIMP
-nsWebSocketHandler::AsyncOpen(nsIURI *aURI,
-                              const nsACString &aOrigin,
-                              nsIWebSocketListener *aListener,
-                              nsISupports *aContext)
+WebSocketChannel::AsyncOpen(nsIURI *aURI,
+                            const nsACString &aOrigin,
+                            nsIWebSocketListener *aListener,
+                            nsISupports *aContext)
 {
-    LOG(("WebSocketHandler::AsyncOpen() %p\n", this));
+  LOG(("WebSocketChannel::AsyncOpen() %p\n", this));
 
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    
-    if (!aURI || !aListener) {
-        LOG(("WebSocketHandler::AsyncOpen() Uri or Listener null"));
-        return NS_ERROR_UNEXPECTED;
-    }
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    if (mListener)
-        return NS_ERROR_ALREADY_OPENED;
+  if (!aURI || !aListener) {
+    LOG(("WebSocketChannel::AsyncOpen() Uri or Listener null"));
+    return NS_ERROR_UNEXPECTED;
+  }
+
+  if (mListener)
+    return NS_ERROR_ALREADY_OPENED;
 
-    nsresult rv;
+  nsresult rv;
 
-    mSocketThread = do_GetService(NS_SOCKETTRANSPORTSERVICE_CONTRACTID, &rv);
-    if (NS_FAILED(rv)) {
-        NS_WARNING("unable to continue without socket transport service");
-        return rv;
-    }
+  mSocketThread = do_GetService(NS_SOCKETTRANSPORTSERVICE_CONTRACTID, &rv);
+  if (NS_FAILED(rv)) {
+    NS_WARNING("unable to continue without socket transport service");
+    return rv;
+  }
 
-    mRandomGenerator = do_GetService("@mozilla.org/security/random-generator;1",
-                                     &rv);
-    if (NS_FAILED(rv)) {
-        NS_WARNING("unable to continue without random number generator");
-        return rv;
-    }
+  mRandomGenerator =
+    do_GetService("@mozilla.org/security/random-generator;1", &rv);
+  if (NS_FAILED(rv)) {
+    NS_WARNING("unable to continue without random number generator");
+    return rv;
+  }
 
-    nsCOMPtr<nsIPrefBranch> prefService;
-    prefService = do_GetService(NS_PREFSERVICE_CONTRACTID);
+  nsCOMPtr<nsIPrefBranch> prefService;
+  prefService = do_GetService(NS_PREFSERVICE_CONTRACTID);
 
-    if (prefService) {
-        PRInt32 intpref;
-        PRBool boolpref;
-        rv = prefService->
-            GetIntPref("network.websocket.max-message-size", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mMaxMessageSize = NS_CLAMP(intpref, 1024, 1 << 30);
-        }
-        rv = prefService->GetIntPref
-            ("network.websocket.timeout.close", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mCloseTimeout = NS_CLAMP(intpref, 1, 1800) * 1000;
-        }
-        rv = prefService->GetIntPref
-            ("network.websocket.timeout.open", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mOpenTimeout = NS_CLAMP(intpref, 1, 1800) * 1000;
-        }
-        rv = prefService->GetIntPref
-            ("network.websocket.timeout.ping.request", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mPingTimeout = NS_CLAMP(intpref, 0, 86400) * 1000;
-        }
-        rv = prefService->GetIntPref
-            ("network.websocket.timeout.ping.response", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mPingResponseTimeout = NS_CLAMP(intpref, 1, 3600) * 1000;
-        }
-        rv = prefService->GetBoolPref
-            ("network.websocket.extensions.stream-deflate", &boolpref);
-        if (NS_SUCCEEDED(rv)) {
-            mAllowCompression = boolpref ? 1 : 0;
-        }
-        rv = prefService->GetBoolPref
-            ("network.websocket.auto-follow-http-redirects", &boolpref);
-        if (NS_SUCCEEDED(rv)) {
-            mAutoFollowRedirects = boolpref ? 1 : 0;
-        }
-        rv = prefService->GetIntPref
-            ("network.websocket.max-connections", &intpref);
-        if (NS_SUCCEEDED(rv)) {
-            mMaxConcurrentConnections = NS_CLAMP(intpref, 1, 0xffff);
-        }
+  if (prefService) {
+    PRInt32 intpref;
+    PRBool boolpref;
+    rv = prefService->GetIntPref("network.websocket.max-message-size", 
+                                 &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mMaxMessageSize = NS_CLAMP(intpref, 1024, 1 << 30);
+    }
+    rv = prefService->GetIntPref("network.websocket.timeout.close", &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mCloseTimeout = NS_CLAMP(intpref, 1, 1800) * 1000;
+    }
+    rv = prefService->GetIntPref("network.websocket.timeout.open", &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mOpenTimeout = NS_CLAMP(intpref, 1, 1800) * 1000;
+    }
+    rv = prefService->GetIntPref("network.websocket.timeout.ping.request",
+                                 &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mPingTimeout = NS_CLAMP(intpref, 0, 86400) * 1000;
+    }
+    rv = prefService->GetIntPref("network.websocket.timeout.ping.response",
+                                 &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mPingResponseTimeout = NS_CLAMP(intpref, 1, 3600) * 1000;
+    }
+    rv = prefService->GetBoolPref("network.websocket.extensions.stream-deflate",
+                                  &boolpref);
+    if (NS_SUCCEEDED(rv)) {
+      mAllowCompression = boolpref ? 1 : 0;
+    }
+    rv = prefService->GetBoolPref("network.websocket.auto-follow-http-redirects",
+                                  &boolpref);
+    if (NS_SUCCEEDED(rv)) {
+      mAutoFollowRedirects = boolpref ? 1 : 0;
+    }
+    rv = prefService->GetIntPref
+      ("network.websocket.max-connections", &intpref);
+    if (NS_SUCCEEDED(rv)) {
+      mMaxConcurrentConnections = NS_CLAMP(intpref, 1, 0xffff);
     }
-    
-    if (sWebSocketAdmissions &&
-        sWebSocketAdmissions->ConnectedCount() >= mMaxConcurrentConnections) {
-        // Checking this early creates an optimal fast-fail, but it is
-        // also a time-of-check-time-of-use problem. So we will check again
-        // after the handshake is complete to catch anything that sneaks
-        // through the race condition.
-        LOG(("nsWebSocketHandler max concurrency %d exceeded",
-             mMaxConcurrentConnections));
-        
-        // WebSocket connections are expected to be long lived, so return
-        // an error here instead of queueing
-        return NS_ERROR_SOCKET_CREATE_FAILED;
-    }
+  }
+
+  if (sWebSocketAdmissions &&
+      sWebSocketAdmissions->ConnectedCount() >= mMaxConcurrentConnections)
+  {
+    // Checking this early creates an optimal fast-fail, but it is
+    // also a time-of-check-time-of-use problem. So we will check again
+    // after the handshake is complete to catch anything that sneaks
+    // through the race condition.
+    LOG(("WebSocketChannel: max concurrency %d exceeded",
+         mMaxConcurrentConnections));
+
+    // WebSocket connections are expected to be long lived, so return
+    // an error here instead of queueing
+    return NS_ERROR_SOCKET_CREATE_FAILED;
+  }
 
-    if (mPingTimeout) {
-        mPingTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
-        if (NS_FAILED(rv)) {
-            NS_WARNING("unable to create ping timer. Carrying on.");
-        }
-        else {
-            LOG(("nsWebSocketHandler will generate ping after %d ms "
-                 "of receive silence\n", mPingTimeout));
-            mPingTimer->SetTarget(mSocketThread);
-            mPingTimer->InitWithCallback(this, mPingTimeout,
-                                         nsITimer::TYPE_ONE_SHOT);
-        }
+  if (mPingTimeout) {
+    mPingTimer = do_CreateInstance("@mozilla.org/timer;1", &rv);
+    if (NS_FAILED(rv)) {
+      NS_WARNING("unable to create ping timer. Carrying on.");
+    } else {
+      LOG(("WebSocketChannel will generate ping after %d ms of receive silence\n",
+           mPingTimeout));
+      mPingTimer->SetTarget(mSocketThread);
+      mPingTimer->InitWithCallback(this, mPingTimeout, nsITimer::TYPE_ONE_SHOT);
     }
+  }
 
-    mOriginalURI = aURI;
-    mURI = mOriginalURI;
-    mListener = aListener;
-    mContext = aContext;
-    mOrigin = aOrigin;
+  mOriginalURI = aURI;
+  mURI = mOriginalURI;
+  mListener = aListener;
+  mContext = aContext;
+  mOrigin = aOrigin;
+
+  nsCOMPtr<nsIURI> localURI;
+  nsCOMPtr<nsIChannel> localChannel;
 
-    nsCOMPtr<nsIURI> localURI;
-    nsCOMPtr<nsIChannel> localChannel;
-    
-    mURI->Clone(getter_AddRefs(localURI));
-    if (mEncrypted)
-        rv = localURI->SetScheme(NS_LITERAL_CSTRING("https"));
-    else
-        rv = localURI->SetScheme(NS_LITERAL_CSTRING("http"));
-    NS_ENSURE_SUCCESS(rv, rv);
-    
-    nsCOMPtr<nsIIOService> ioService;
-    ioService = do_GetService(NS_IOSERVICE_CONTRACTID, &rv);
-    if (NS_FAILED(rv)) {
-        NS_WARNING("unable to continue without io service");
-        return rv;
-    }
+  mURI->Clone(getter_AddRefs(localURI));
+  if (mEncrypted)
+    rv = localURI->SetScheme(NS_LITERAL_CSTRING("https"));
+  else
+    rv = localURI->SetScheme(NS_LITERAL_CSTRING("http"));
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    nsCOMPtr<nsIIOService2> io2 = do_QueryInterface(ioService, &rv);
-    if (NS_FAILED(rv)) {
-        NS_WARNING("unable to continue without ioservice2 interface");
-        return rv;
-    }
+  nsCOMPtr<nsIIOService> ioService;
+  ioService = do_GetService(NS_IOSERVICE_CONTRACTID, &rv);
+  if (NS_FAILED(rv)) {
+    NS_WARNING("unable to continue without io service");
+    return rv;
+  }
+
+  nsCOMPtr<nsIIOService2> io2 = do_QueryInterface(ioService, &rv);
+  if (NS_FAILED(rv)) {
+    NS_WARNING("WebSocketChannel: unable to continue without ioservice2");
+    return rv;
+  }
 
-    rv = io2->NewChannelFromURIWithProxyFlags(
-        localURI,
-        mURI,
-        nsIProtocolProxyService::RESOLVE_PREFER_SOCKS_PROXY |
-        nsIProtocolProxyService::RESOLVE_PREFER_HTTPS_PROXY |
-        nsIProtocolProxyService::RESOLVE_ALWAYS_TUNNEL,
-        getter_AddRefs(localChannel));
-    NS_ENSURE_SUCCESS(rv, rv);
+  rv = io2->NewChannelFromURIWithProxyFlags(
+              localURI,
+              mURI,
+              nsIProtocolProxyService::RESOLVE_PREFER_SOCKS_PROXY |
+              nsIProtocolProxyService::RESOLVE_PREFER_HTTPS_PROXY |
+              nsIProtocolProxyService::RESOLVE_ALWAYS_TUNNEL,
+              getter_AddRefs(localChannel));
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    // pass most GetInterface() requests through to our instantiator, but handle
-    // nsIChannelEventSink in this object in order to deal with redirects
-    localChannel->SetNotificationCallbacks(this);
+  // Pass most GetInterface() requests through to our instantiator, but handle
+  // nsIChannelEventSink in this object in order to deal with redirects
+  localChannel->SetNotificationCallbacks(this);
 
-    mChannel = do_QueryInterface(localChannel, &rv);
-    NS_ENSURE_SUCCESS(rv, rv);
+  mChannel = do_QueryInterface(localChannel, &rv);
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    mHttpChannel = do_QueryInterface(localChannel, &rv);
-    NS_ENSURE_SUCCESS(rv, rv);
-    
-    rv = SetupRequest();
-    if (NS_FAILED(rv))
-        return rv;
+  mHttpChannel = do_QueryInterface(localChannel, &rv);
+  NS_ENSURE_SUCCESS(rv, rv);
 
-    return ApplyForAdmission();
+  rv = SetupRequest();
+  if (NS_FAILED(rv))
+    return rv;
+
+  return ApplyForAdmission();
 }
 
 NS_IMETHODIMP
-nsWebSocketHandler::Close()
+WebSocketChannel::Close()
 {
-    LOG(("WebSocketHandler::Close() %p\n", this));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    if (mRequestedClose) {
-        LOG(("WebSocketHandler:: Double close error\n"));
-        return NS_ERROR_UNEXPECTED;
-    }
+  LOG(("WebSocketChannel::Close() %p\n", this));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  if (mRequestedClose) {
+    LOG(("WebSocketChannel:: Double close error\n"));
+    return NS_ERROR_UNEXPECTED;
+  }
 
-    mRequestedClose = 1;
-    
-    nsCOMPtr<nsIRunnable> event =
-        new nsPostMessage(this, kFinMessage, -1);
-    return mSocketThread->Dispatch(event, nsIEventTarget::DISPATCH_NORMAL);
+  mRequestedClose = 1;
 
-    return NS_OK;
+  return mSocketThread->Dispatch(new nsPostMessage(this, kFinMessage, -1),
+                                 nsIEventTarget::DISPATCH_NORMAL);
 }
 
 NS_IMETHODIMP
-nsWebSocketHandler::SendMsg(const nsACString &aMsg)
+WebSocketChannel::SendMsg(const nsACString &aMsg)
 {
-    LOG(("WebSocketHandler::SendMsg() %p\n", this));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  LOG(("WebSocketChannel::SendMsg() %p\n", this));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    if (mRequestedClose) {
-        LOG(("WebSocketHandler:: SendMsg when closed error\n"));
-        return NS_ERROR_UNEXPECTED;
-    }
+  if (mRequestedClose) {
+    LOG(("WebSocketChannel:: SendMsg when closed error\n"));
+    return NS_ERROR_UNEXPECTED;
+  }
 
-    if (mStopped) {
-        LOG(("WebSocketHandler:: SendMsg when stopped error\n"));
-        return NS_ERROR_NOT_CONNECTED;
-    }
-    
-    nsCOMPtr<nsIRunnable> event =
-        new nsPostMessage(this, new nsCString(aMsg), -1);
-    return mSocketThread->Dispatch(event, nsIEventTarget::DISPATCH_NORMAL);
+  if (mStopped) {
+    LOG(("WebSocketChannel:: SendMsg when stopped error\n"));
+    return NS_ERROR_NOT_CONNECTED;
+  }
+
+  return mSocketThread->Dispatch(
+                          new nsPostMessage(this, new nsCString(aMsg), -1),
+                          nsIEventTarget::DISPATCH_NORMAL);
 }
 
 NS_IMETHODIMP
-nsWebSocketHandler::SendBinaryMsg(const nsACString &aMsg)
+WebSocketChannel::SendBinaryMsg(const nsACString &aMsg)
 {
-    LOG(("WebSocketHandler::SendBinaryMsg() %p len=%d\n", this, aMsg.Length()));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  LOG(("WebSocketChannel::SendBinaryMsg() %p len=%d\n", this, aMsg.Length()));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
 
-    if (mRequestedClose) {
-        LOG(("WebSocketHandler:: SendBinaryMsg when closed error\n"));
-        return NS_ERROR_UNEXPECTED;
-    }
+  if (mRequestedClose) {
+    LOG(("WebSocketChannel:: SendBinaryMsg when closed error\n"));
+    return NS_ERROR_UNEXPECTED;
+  }
 
-    if (mStopped) {
-        LOG(("WebSocketHandler:: SendBinaryMsg when stopped error\n"));
-        return NS_ERROR_NOT_CONNECTED;
-    }
-    
-    nsCOMPtr<nsIRunnable> event =
-        new nsPostMessage(this, new nsCString(aMsg), aMsg.Length());
-    return mSocketThread->Dispatch(event, nsIEventTarget::DISPATCH_NORMAL);
+  if (mStopped) {
+    LOG(("WebSocketChannel:: SendBinaryMsg when stopped error\n"));
+    return NS_ERROR_NOT_CONNECTED;
+  }
+
+  return mSocketThread->Dispatch(new nsPostMessage(this, new nsCString(aMsg), 
+                                                   aMsg.Length()),
+                                 nsIEventTarget::DISPATCH_NORMAL);
 }
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnTransportAvailable(nsISocketTransport *aTransport,
+WebSocketChannel::OnTransportAvailable(nsISocketTransport *aTransport,
                                          nsIAsyncInputStream *aSocketIn,
                                          nsIAsyncOutputStream *aSocketOut)
 {
-    LOG(("WebSocketHandler::OnTransportAvailable "
-         "%p [%p %p %p] rcvdonstart=%d\n",
-         this, aTransport, aSocketIn, aSocketOut, mRecvdHttpOnStartRequest));
+  LOG(("WebSocketChannel::OnTransportAvailable %p [%p %p %p] rcvdonstart=%d\n",
+       this, aTransport, aSocketIn, aSocketOut, mRecvdHttpOnStartRequest));
+
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  NS_ABORT_IF_FALSE(!mRecvdHttpUpgradeTransport, "OTA duplicated");
+  NS_ABORT_IF_FALSE(aSocketIn, "OTA with invalid socketIn");
 
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    NS_ABORT_IF_FALSE(!mRecvdHttpUpgradeTransport, "OTA duplicated");
-    NS_ABORT_IF_FALSE(aSocketIn, "OTA with invalid socketIn");
-    
-    mTransport = aTransport;
-    mSocketIn = aSocketIn;
-    mSocketOut = aSocketOut;
-    if (sWebSocketAdmissions)
-        sWebSocketAdmissions->IncrementConnectedCount();
+  mTransport = aTransport;
+  mSocketIn = aSocketIn;
+  mSocketOut = aSocketOut;
+  if (sWebSocketAdmissions)
+    sWebSocketAdmissions->IncrementConnectedCount();
 
-    nsresult rv;
-    rv = mTransport->SetEventSink(nsnull, nsnull);
-    if (NS_FAILED(rv)) return rv;
-    rv = mTransport->SetSecurityCallbacks(mCallbacks);
-    if (NS_FAILED(rv)) return rv;
+  nsresult rv;
+  rv = mTransport->SetEventSink(nsnull, nsnull);
+  if (NS_FAILED(rv)) return rv;
+  rv = mTransport->SetSecurityCallbacks(mCallbacks);
+  if (NS_FAILED(rv)) return rv;
 
-    mRecvdHttpUpgradeTransport = 1;
-    if (mRecvdHttpOnStartRequest)
-        return StartWebsocketData();
-    return NS_OK;
+  mRecvdHttpUpgradeTransport = 1;
+  if (mRecvdHttpOnStartRequest)
+    return StartWebsocketData();
+  return NS_OK;
 }
 
 // nsIRequestObserver (from nsIStreamListener)
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnStartRequest(nsIRequest *aRequest,
+WebSocketChannel::OnStartRequest(nsIRequest *aRequest,
                                    nsISupports *aContext)
 {
-    LOG(("WebSocketHandler::OnStartRequest() %p [%p %p] recvdhttpupgrade=%d\n",
-         this, aRequest, aContext, mRecvdHttpUpgradeTransport));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    NS_ABORT_IF_FALSE(!mRecvdHttpOnStartRequest, "OTA duplicated");
+  LOG(("WebSocketChannel::OnStartRequest(): %p [%p %p] recvdhttpupgrade=%d\n",
+       this, aRequest, aContext, mRecvdHttpUpgradeTransport));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+  NS_ABORT_IF_FALSE(!mRecvdHttpOnStartRequest, "OTA duplicated");
+
+  // Generating the onStart event will take us out of the
+  // CONNECTING state which means we can now open another,
+  // perhaps parallel, connection to the same host if one
+  // is pending
 
-    // Generating the onStart event will take us out of the
-    // CONNECTING state which means we can now open another,
-    // perhaps parallel, connection to the same host if one
-    // is pending
+  if (sWebSocketAdmissions->Complete(mAddress))
+    LOG(("WebSocketChannel::OnStartRequest: Starting Pending Open\n"));
+  else
+    LOG(("WebSocketChannel::OnStartRequest: No More Pending Opens\n"));
 
-    if (sWebSocketAdmissions->Complete(mAddress))
-        LOG(("nsWebSocketHandler::OnStartRequest Starting Pending Open\n"));
-    else
-        LOG(("nsWebSocketHandler::OnStartRequest No More Pending Opens\n"));
+  if (mOpenTimer) {
+    mOpenTimer->Cancel();
+    mOpenTimer = nsnull;
+  }
 
-    if (mOpenTimer) {
-        mOpenTimer->Cancel();
-        mOpenTimer = nsnull;
-    }
+  if (mStopped) {
+    LOG(("WebSocketChannel::OnStartRequest: Channel Already Done\n"));
+    AbortSession(NS_ERROR_CONNECTION_REFUSED);
+    return NS_ERROR_CONNECTION_REFUSED;
+  }
+
+  nsresult rv;
+  PRUint32 status;
+  char *val, *token;
 
-    if (mStopped) {
-        LOG(("WebSocketHandler::OnStartRequest Handler Already Done\n"));
-        AbortSession(NS_ERROR_CONNECTION_REFUSED);
-        return NS_ERROR_CONNECTION_REFUSED;
-    }
+  rv = mHttpChannel->GetResponseStatus(&status);
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel::OnStartRequest: No HTTP Response\n"));
+    AbortSession(NS_ERROR_CONNECTION_REFUSED);
+    return NS_ERROR_CONNECTION_REFUSED;
+  }
 
-    nsresult rv;
-    PRUint32 status;
-    char *val, *token;
+  LOG(("WebSocketChannel::OnStartRequest: HTTP status %d\n", status));
+  if (status != 101) {
+    AbortSession(NS_ERROR_CONNECTION_REFUSED);
+    return NS_ERROR_CONNECTION_REFUSED;
+  }
+
+  nsCAutoString respUpgrade;
+  rv = mHttpChannel->GetResponseHeader(
+    NS_LITERAL_CSTRING("Upgrade"), respUpgrade);
 
-    rv = mHttpChannel->GetResponseStatus(&status);
-    if (NS_FAILED(rv)) {
-        LOG(("WebSocketHandler::OnStartRequest No HTTP Response\n"));
-        AbortSession(NS_ERROR_CONNECTION_REFUSED);
-        return NS_ERROR_CONNECTION_REFUSED;
+  if (NS_SUCCEEDED(rv)) {
+    rv = NS_ERROR_ILLEGAL_VALUE;
+    if (!respUpgrade.IsEmpty()) {
+      val = respUpgrade.BeginWriting();
+      while ((token = nsCRT::strtok(val, ", \t", &val))) {
+        if (PL_strcasecmp(token, "Websocket") == 0) {
+          rv = NS_OK;
+          break;
+        }
+      }
     }
+  }
 
-    LOG(("WebSocketHandler::OnStartRequest HTTP status %d\n", status));
-    if (status != 101) {
-        AbortSession(NS_ERROR_CONNECTION_REFUSED);
-        return NS_ERROR_CONNECTION_REFUSED;
-    }
-    
-    nsCAutoString respUpgrade;
-    rv = mHttpChannel->GetResponseHeader(
-        NS_LITERAL_CSTRING("Upgrade"), respUpgrade);
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel::OnStartRequest: "
+         "HTTP response header Upgrade: websocket not found\n"));
+    AbortSession(rv);
+    return rv;
+  }
+
+  nsCAutoString respConnection;
+  rv = mHttpChannel->GetResponseHeader(
+    NS_LITERAL_CSTRING("Connection"), respConnection);
 
-    if (NS_SUCCEEDED(rv)) {
-        rv = NS_ERROR_ILLEGAL_VALUE;
-        if (!respUpgrade.IsEmpty()) {
-            val = respUpgrade.BeginWriting();
-            while ((token = nsCRT::strtok(val, ", \t", &val))) {
-                if (PL_strcasecmp(token, "Websocket") == 0) {
-                    rv = NS_OK;
-                    break;
-                }
-            }
+  if (NS_SUCCEEDED(rv)) {
+    rv = NS_ERROR_ILLEGAL_VALUE;
+    if (!respConnection.IsEmpty()) {
+      val = respConnection.BeginWriting();
+      while ((token = nsCRT::strtok(val, ", \t", &val))) {
+        if (PL_strcasecmp(token, "Upgrade") == 0) {
+          rv = NS_OK;
+          break;
         }
+      }
     }
-    
-    if (NS_FAILED(rv)) {
-        LOG(("WebSocketHandler::OnStartRequest "
-             "HTTP response header Upgrade: websocket not found\n"));
-        AbortSession(rv);
-        return rv;
-    }
+  }
+
+  if (NS_FAILED(rv)) {
+    LOG(("WebSocketChannel::OnStartRequest: "
+         "HTTP response header 'Connection: Upgrade' not found\n"));
+    AbortSession(rv);
+    return rv;
+  }
+
+  nsCAutoString respAccept;
+  rv = mHttpChannel->GetResponseHeader(
+                       NS_LITERAL_CSTRING("Sec-WebSocket-Accept"),
+                       respAccept);
 
-    nsCAutoString respConnection;
+  if (NS_FAILED(rv) ||
+    respAccept.IsEmpty() || !respAccept.Equals(mHashedSecret)) {
+    LOG(("WebSocketChannel::OnStartRequest: "
+         "HTTP response header Sec-WebSocket-Accept check failed\n"));
+    LOG(("WebSocketChannel::OnStartRequest: Expected %s recevied %s\n",
+         mHashedSecret.get(), respAccept.get()));
+    AbortSession(NS_ERROR_ILLEGAL_VALUE);
+    return NS_ERROR_ILLEGAL_VALUE;
+  }
+
+  // If we sent a sub protocol header, verify the response matches
+  // If it does not, set mProtocol to "" so the protocol attribute
+  // of the WebSocket JS object reflects that
+  if (!mProtocol.IsEmpty()) {
+    nsCAutoString respProtocol;
     rv = mHttpChannel->GetResponseHeader(
-        NS_LITERAL_CSTRING("Connection"), respConnection);
-
+                         NS_LITERAL_CSTRING("Sec-WebSocket-Protocol"), 
+                         respProtocol);
     if (NS_SUCCEEDED(rv)) {
-        rv = NS_ERROR_ILLEGAL_VALUE;
-        if (!respConnection.IsEmpty()) {
-            val = respConnection.BeginWriting();
-            while ((token = nsCRT::strtok(val, ", \t", &val))) {
-                if (PL_strcasecmp(token, "Upgrade") == 0) {
-                    rv = NS_OK;
-                    break;
-                }
-            }
+      rv = NS_ERROR_ILLEGAL_VALUE;
+      val = mProtocol.BeginWriting();
+      while ((token = nsCRT::strtok(val, ", \t", &val))) {
+        if (PL_strcasecmp(token, respProtocol.get()) == 0) {
+          rv = NS_OK;
+          break;
         }
-    }
-    
-    if (NS_FAILED(rv)) {
-        LOG(("WebSocketHandler::OnStartRequest "
-             "HTTP response header Connection: Upgrade not found\n"));
-        AbortSession(rv);
-        return rv;
-    }
-
-    nsCAutoString respAccept;
-    rv = mHttpChannel->GetResponseHeader(
-        NS_LITERAL_CSTRING("Sec-WebSocket-Accept"), respAccept);
+      }
 
-    if (NS_FAILED(rv) ||
-        respAccept.IsEmpty() || !respAccept.Equals(mHashedSecret)) {
-        LOG(("WebSocketHandler::OnStartRequest "
-             "HTTP response header Sec-WebSocket-Accept check failed\n"));
-        LOG(("WebSocketHandler::OnStartRequest "
-             "Expected %s recevied %s\n",
-             mHashedSecret.get(), respAccept.get()));
-        AbortSession(NS_ERROR_ILLEGAL_VALUE);
-        return NS_ERROR_ILLEGAL_VALUE;
-    }
-
-    // If we sent a sub protocol header, verify the response matches
-    // If it does not, set mProtocol to "" so the protocol attribute
-    // of the WebSocket JS object reflects that
-    if (!mProtocol.IsEmpty()) {
-        nsCAutoString respProtocol;
-        rv = mHttpChannel->GetResponseHeader(
-            NS_LITERAL_CSTRING("Sec-WebSocket-Protocol"), respProtocol);
-        if (NS_SUCCEEDED(rv)) {
-            rv = NS_ERROR_ILLEGAL_VALUE;
-            val = mProtocol.BeginWriting();
-            while ((token = nsCRT::strtok(val, ", \t", &val))) {
-                if (PL_strcasecmp(token, respProtocol.get()) == 0) {
-                    rv = NS_OK;
-                    break;
-                }
-            }
-
-            if (NS_SUCCEEDED(rv)) {
-                LOG(("WebsocketHandler::OnStartRequest "
-                     "subprotocol %s confirmed", respProtocol.get()));
-                mProtocol = respProtocol;
-            }
-            else {
-                LOG(("WebsocketHandler::OnStartRequest "
-                     "subprotocol [%s] not found - %s returned",
-                     mProtocol.get(), respProtocol.get()));
-                mProtocol.Truncate();
-            }
-        }
-        else {
-            LOG(("WebsocketHandler::OnStartRequest "
+      if (NS_SUCCEEDED(rv)) {
+        LOG(("WebsocketChannel::OnStartRequest: subprotocol %s confirmed",
+             respProtocol.get()));
+        mProtocol = respProtocol;
+      } else {
+        LOG(("WebsocketChannel::OnStartRequest: "
+             "subprotocol [%s] not found - %s returned",
+             mProtocol.get(), respProtocol.get()));
+        mProtocol.Truncate();
+      }
+    } else {
+      LOG(("WebsocketChannel::OnStartRequest "
                  "subprotocol [%s] not found - none returned",
                  mProtocol.get()));
-            mProtocol.Truncate();
-        }
+      mProtocol.Truncate();
     }
+  }
+
+  rv = HandleExtensions();
+  if (NS_FAILED(rv))
+    return rv;
 
-    rv = HandleExtensions();
-    if (NS_FAILED(rv))
-        return rv;
-    
-    LOG(("WebSocketHandler::OnStartRequest Notifying Listener %p\n",
-         mListener.get()));
-    
-    if (mListener)
-        mListener->OnStart(mContext);
+  LOG(("WebSocketChannel::OnStartRequest: Notifying Listener %p\n",
+       mListener.get()));
+
+  if (mListener)
+    mListener->OnStart(mContext);
 
-    mRecvdHttpOnStartRequest = 1;
-    if (mRecvdHttpUpgradeTransport)
-        return StartWebsocketData();
+  mRecvdHttpOnStartRequest = 1;
+  if (mRecvdHttpUpgradeTransport)
+    return StartWebsocketData();
 
-    return NS_OK;
+  return NS_OK;
 }
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnStopRequest(nsIRequest *aRequest,
+WebSocketChannel::OnStopRequest(nsIRequest *aRequest,
                                   nsISupports *aContext,
                                   nsresult aStatusCode)
 {
-    LOG(("WebSocketHandler::OnStopRequest() %p [%p %p %x]\n",
-         this, aRequest, aContext, aStatusCode));
-    NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
-    
-    // this is the stop of the HTTP upgrade transaction, the
-    // upgraded streams live on
+  LOG(("WebSocketChannel::OnStopRequest() %p [%p %p %x]\n",
+       this, aRequest, aContext, aStatusCode));
+  NS_ABORT_IF_FALSE(NS_IsMainThread(), "not main thread");
+
+  // This is the end of the HTTP upgrade transaction, the
+  // upgraded streams live on
 
-    mChannel = nsnull;
-    mHttpChannel = nsnull;
-    mLoadGroup = nsnull;
-    mCallbacks = nsnull;
-    
-    return NS_OK;
+  mChannel = nsnull;
+  mHttpChannel = nsnull;
+  mLoadGroup = nsnull;
+  mCallbacks = nsnull;
+
+  return NS_OK;
 }
 
 // nsIInputStreamCallback
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnInputStreamReady(nsIAsyncInputStream *aStream)
+WebSocketChannel::OnInputStreamReady(nsIAsyncInputStream *aStream)
 {
-    LOG(("WebSocketHandler::OnInputStreamReady() %p\n", this));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    
-    nsRefPtr<nsIStreamListener>    deleteProtector1(mInflateReader);
-    nsRefPtr<nsIStringInputStream> deleteProtector2(mInflateStream);
+  LOG(("WebSocketChannel::OnInputStreamReady() %p\n", this));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+
+  nsRefPtr<nsIStreamListener>    deleteProtector1(mInflateReader);
+  nsRefPtr<nsIStringInputStream> deleteProtector2(mInflateStream);
+
+  // this is after the  http upgrade - so we are speaking websockets
+  char  buffer[2048];
+  PRUint32 count;
+  nsresult rv;
 
-    // this is after the  http upgrade - so we are speaking websockets
-    char  buffer[2048];
-    PRUint32 count;
-    nsresult rv;
+  do {
+    rv = mSocketIn->Read((char *)buffer, 2048, &count);
+    LOG(("WebSocketChannel::OnInputStreamReady: read %u rv %x\n", count, rv));
 
-    do {
-        rv = mSocketIn->Read((char *)buffer, 2048, &count);
-        LOG(("WebSocketHandler::OnInputStreamReady read %u rv %x\n",
-             count, rv));
+    if (rv == NS_BASE_STREAM_WOULD_BLOCK) {
+      mSocketIn->AsyncWait(this, 0, 0, mSocketThread);
+      return NS_OK;
+    }
+
+    if (NS_FAILED(rv)) {
+      mTCPClosed = PR_TRUE;
+      AbortSession(rv);
+      return rv;
+    }
 
-        if (rv == NS_BASE_STREAM_WOULD_BLOCK) {
-            mSocketIn->AsyncWait(this, 0, 0, mSocketThread);
-            return NS_OK;
-        }
-        
-        if (NS_FAILED(rv)) {
-            mTCPClosed = PR_TRUE;
-            AbortSession(rv);
-            return rv;
-        }
-        
-        if (count == 0) {
-            mTCPClosed = PR_TRUE;
-            AbortSession(NS_BASE_STREAM_CLOSED);
-            return NS_OK;
-        }
-        
-        if (mStopped) {
-            NS_ABORT_IF_FALSE(mLingeringCloseTimer,
-                              "OnInputReady after stop without linger");
-            continue;
-        }
-        
-        if (mInflateReader) {
-            mInflateStream->ShareData(buffer, count);
-            rv = mInflateReader->OnDataAvailable(nsnull, mSocketIn,
-                                                 mInflateStream, 0, count);
-        }
-        else {
-            rv = ProcessInput((PRUint8 *)buffer, count);
-        }
+    if (count == 0) {
+      mTCPClosed = PR_TRUE;
+      AbortSession(NS_BASE_STREAM_CLOSED);
+      return NS_OK;
+    }
+
+    if (mStopped) {
+      NS_ABORT_IF_FALSE(mLingeringCloseTimer,
+                        "OnInputReady after stop without linger");
+      continue;
+    }
 
-        if (NS_FAILED(rv)) {
-            AbortSession(rv);
-            return rv;
-        }
+    if (mInflateReader) {
+      mInflateStream->ShareData(buffer, count);
+      rv = mInflateReader->OnDataAvailable(nsnull, mSocketIn, mInflateStream, 
+                                           0, count);
+    } else {
+      rv = ProcessInput((PRUint8 *)buffer, count);
+    }
 
-    } while (NS_SUCCEEDED(rv) && mSocketIn);
+    if (NS_FAILED(rv)) {
+      AbortSession(rv);
+      return rv;
+    }
+  } while (NS_SUCCEEDED(rv) && mSocketIn);
 
-    return NS_OK;
+  return NS_OK;
 }
 
 
 // nsIOutputStreamCallback
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnOutputStreamReady(nsIAsyncOutputStream *aStream)
+WebSocketChannel::OnOutputStreamReady(nsIAsyncOutputStream *aStream)
 {
-    LOG(("WebSocketHandler::OnOutputStreamReady() %p\n", this));
-    NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread,
-                      "not socket thread");
-    nsresult rv;
+  LOG(("WebSocketChannel::OnOutputStreamReady() %p\n", this));
+  NS_ABORT_IF_FALSE(PR_GetCurrentThread() == gSocketThread, "not socket thread");
+  nsresult rv;
 
-    if (!mCurrentOut)
-        PrimeNewOutgoingMessage();
+  if (!mCurrentOut)
+    PrimeNewOutgoingMessage();
 
-    while (mCurrentOut && mSocketOut) {
-        const char *sndBuf;
-        PRUint32 toSend;
-        PRUint32 amtSent;
-        
-        if (mHdrOut) {
-            sndBuf = (const char *)mHdrOut;
-            toSend = mHdrOutToSend;
-            LOG(("WebSocketHandler::OnOutputStreamReady "
-                 "Try to send %u of hdr/copybreak\n",
-                 toSend));
-        }
-        else {
-            sndBuf = (char *) mCurrentOut->BeginReading() + mCurrentOutSent;
-            toSend = mCurrentOut->Length() - mCurrentOutSent;
-            if (toSend > 0) {
-                LOG(("WebSocketHandler::OnOutputStreamReady "
-                     "Try to send %u of data\n",
-                     toSend));
-            }
-        }
-        
-        if (toSend == 0) {
-            amtSent = 0;
-        }
-        else {
-            rv = mSocketOut->Write(sndBuf, toSend, &amtSent);
-            LOG(("WebSocketHandler::OnOutputStreamReady write %u rv %x\n",
-                 amtSent, rv));
-        
-            if (rv == NS_BASE_STREAM_WOULD_BLOCK) {
-                mSocketOut->AsyncWait(this, 0, 0, nsnull);
-                return NS_OK;
-            }
+  while (mCurrentOut && mSocketOut) {
+    const char *sndBuf;
+    PRUint32 toSend;
+    PRUint32 amtSent;
 
-            if (NS_FAILED(rv)) {
-                AbortSession(rv);
-                return NS_OK;
-            }
-        }
-        
-        if (mHdrOut) {
-            if (amtSent == toSend) {
-                mHdrOut = nsnull;
-                mHdrOutToSend = 0;
-            }
-            else {
-                mHdrOut += amtSent;
-                mHdrOutToSend -= amtSent;
-            }
-        }
-        else {
-            if (amtSent == toSend) {
-                if (!mStopped) {
-                    nsCOMPtr<nsIRunnable> event =
-                        new CallAcknowledge(mListener, mContext,
-                                            mCurrentOut->Length());
-                    NS_DispatchToMainThread(event);
-                }
-                delete mCurrentOut;
-                mCurrentOut = nsnull;
-                mCurrentOutSent = 0;
-                PrimeNewOutgoingMessage();
-            }
-            else {
-                mCurrentOutSent += amtSent;
-            }
-        }
+    if (mHdrOut) {
+      sndBuf = (const char *)mHdrOut;
+      toSend = mHdrOutToSend;
+      LOG(("WebSocketChannel::OnOutputStreamReady: "
+           "Try to send %u of hdr/copybreak\n", toSend));
+    } else {
+      sndBuf = (char *) mCurrentOut->BeginReading() + mCurrentOutSent;
+      toSend = mCurrentOut->Length() - mCurrentOutSent;
+      if (toSend > 0) {
+        LOG(("WebSocketChannel::OnOutputStreamReady: "
+             "Try to send %u of data\n", toSend));
+      }
     }
 
-    if (mReleaseOnTransmit)
-        ReleaseSession();
-    return NS_OK;
+    if (toSend == 0) {
+      amtSent = 0;
+    } else {
+      rv = mSocketOut->Write(sndBuf, toSend, &amtSent);
+      LOG(("WebSocketChannel::OnOutputStreamReady: write %u rv %x\n",
+           amtSent, rv));
+
+      if (rv == NS_BASE_STREAM_WOULD_BLOCK) {
+        mSocketOut->AsyncWait(this, 0, 0, nsnull);
+        return NS_OK;
+      }
+
+      if (NS_FAILED(rv)) {
+        AbortSession(rv);
+        return NS_OK;
+      }
+    }
+
+    if (mHdrOut) {
+      if (amtSent == toSend) {
+        mHdrOut = nsnull;
+        mHdrOutToSend = 0;
+      } else {
+        mHdrOut += amtSent;
+        mHdrOutToSend -= amtSent;
+      }
+    } else {
+      if (amtSent == toSend) {
+        if (!mStopped) {
+          NS_DispatchToMainThread(new CallAcknowledge(mListener, mContext,
+                                                      mCurrentOut->Length()));
+        }
+        delete mCurrentOut;
+        mCurrentOut = nsnull;
+        mCurrentOutSent = 0;
+        PrimeNewOutgoingMessage();
+      } else {
+        mCurrentOutSent += amtSent;
+      }
+    }
+  }
+
+  if (mReleaseOnTransmit)
+    ReleaseSession();
+  return NS_OK;
 }
 
 // nsIStreamListener
 
 NS_IMETHODIMP
-nsWebSocketHandler::OnDataAvailable(nsIRequest *aRequest,
+WebSocketChannel::OnDataAvailable(nsIRequest *aRequest,
                                     nsISupports *aContext,
                                     nsIInputStream *aInputStream,
                                     PRUint32 aOffset,
                                     PRUint32 aCount)
 {
-    LOG(("WebSocketHandler::OnDataAvailable() %p [%p %p %p %u %u]\n",
+  LOG(("WebSocketChannel::OnDataAvailable() %p [%p %p %p %u %u]\n",
          this, aRequest, aContext, aInputStream, aOffset, aCount));
 
-    if (aContext == mSocketIn) {
-        // This is the deflate decoder
+  if (aContext == mSocketIn) {
+    // This is the deflate decoder
 
-        LOG(("WebSocketHandler::OnDataAvailable Deflate Data %u\n",
+    LOG(("WebSocketChannel::OnDataAvailable: Deflate Data %u\n",
              aCount));
 
-        PRUint8  buffer[2048];
-        PRUint32 maxRead;
-        PRUint32 count;
-        nsresult rv;
+    PRUint8  buffer[2048];
+    PRUint32 maxRead;
+    PRUint32 count;
+    nsresult rv;
+
+    while (aCount > 0) {
+      if (mStopped)
+        return NS_BASE_STREAM_CLOSED;
 
-        while (aCount > 0) {
-            if (mStopped)
-                return NS_BASE_STREAM_CLOSED;
-            
-            maxRead = NS_MIN(2048U, aCount);
-            rv = aInputStream->Read((char *)buffer, maxRead, &count);
-            LOG(("WebSocketHandler::OnDataAvailable "
-                 "InflateRead read %u rv %x\n",
-                 count, rv));
-            if (NS_FAILED(rv) || count == 0) {
-                AbortSession(rv);
-                break;
-            }
-            
-            aCount -= count;
-            rv = ProcessInput(buffer, count);
-        }
-        return NS_OK;
+      maxRead = NS_MIN(2048U, aCount);
+      rv = aInputStream->Read((char *)buffer, maxRead, &count);
+      LOG(("WebSocketChannel::OnDataAvailable: InflateRead read %u rv %x\n",
+           count, rv));
+      if (NS_FAILED(rv) || count == 0) {
+        AbortSession(rv);
+        break;
+      }
+
+      aCount -= count;
+      rv = ProcessInput(buffer, count);
     }
+    return NS_OK;
+  }
+
+  if (aContext == mSocketOut) {
+    // This is the deflate encoder
 
-    if (aContext == mSocketOut) {
-        // This is the deflate encoder
-        
-        PRUint32 maxRead;
-        PRUint32 count;
-        nsresult rv;
+    PRUint32 maxRead;
+    PRUint32 count;
+    nsresult rv;
 
-        while (aCount > 0) {
-            if (mStopped)
-                return NS_BASE_STREAM_CLOSED;
+    while (aCount > 0) {
+      if (mStopped)
+        return NS_BASE_STREAM_CLOSED;
 
-            maxRead = NS_MIN(2048U, aCount);
-            EnsureHdrOut(mHdrOutToSend + aCount);
-            rv = aInputStream->Read((char *)mHdrOut + mHdrOutToSend,
-                                    maxRead, &count);
-            LOG(("WebSocketHandler::OnDataAvailable "
-                 "DeflateWrite read %u rv %x\n", count, rv));
-            if (NS_FAILED(rv) || count == 0) {
-                AbortSession(rv);
-                break;
-            }
+      maxRead = NS_MIN(2048U, aCount);
+      EnsureHdrOut(mHdrOutToSend + aCount);
+      rv = aInputStream->Read((char *)mHdrOut + mHdrOutToSend, maxRead, &count);
+      LOG(("WebSocketChannel::OnDataAvailable: DeflateWrite read %u rv %x\n", 
+           count, rv));
+      if (NS_FAILED(rv) || count == 0) {
+        AbortSession(rv);
+        break;
+      }
 
-            mHdrOutToSend += count;
-            aCount -= count;
-        }
-        return NS_OK;
+      mHdrOutToSend += count;
+      aCount -= count;
     }
-    
+    return NS_OK;
+  }
+
 
-    // Otherwise, this is the HTTP OnDataAvailable Method, which means
-    // this is http data in response to the upgrade request and
-    // there should be no http response body if the upgrade succeeded
+  // Otherwise, this is the HTTP OnDataAvailable Method, which means
+  // this is http data in response to the upgrade request and
+  // there should be no http response body if the upgrade succeeded
 
-    // This generally should be caught by a non 101 response code in
-    // OnStartRequest().. so we can ignore the data here
+  // This generally should be caught by a non 101 response code in
+  // OnStartRequest().. so we can ignore the data here
 
-    LOG(("WebSocketHandler::OnDataAvailable HTTP data unexpected len>=%u\n",
+  LOG(("WebSocketChannel::OnDataAvailable: HTTP data unexpected len>=%u\n",
          aCount));
 
-    return NS_OK;
+  return NS_OK;
 }
 
 } // namespace mozilla::net
 } // namespace mozilla
diff --git a/netwerk/protocol/websocket/nsWebSocketHandler.h b/netwerk/protocol/websocket/WebSocketChannel.h
rename from netwerk/protocol/websocket/nsWebSocketHandler.h
rename to netwerk/protocol/websocket/WebSocketChannel.h
--- a/netwerk/protocol/websocket/nsWebSocketHandler.h
+++ b/netwerk/protocol/websocket/WebSocketChannel.h
@@ -1,9 +1,10 @@
 /* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
+/* vim: set sw=2 ts=8 et tw=80 : */
 /* ***** BEGIN LICENSE BLOCK *****
  * Version: MPL 1.1/GPL 2.0/LGPL 2.1
  *
  * The contents of this file are subject to the Mozilla Public License Version
  * 1.1 (the "License"); you may not use this file except in compliance with
  * the License. You may obtain a copy of the License at
  * http://www.mozilla.org/MPL/
  *
@@ -32,20 +33,19 @@
  * use your version of this file under the terms of the MPL, indicate your
  * decision by deleting the provisions above and replace them with the notice
  * and other provisions required by the GPL or the LGPL. If you do not delete
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
-#ifndef mozilla_net_nsWebSocketHandler_h
-#define mozilla_net_nsWebSocketHandler_h
+#ifndef mozilla_net_WebSocketChannel_h
+#define mozilla_net_WebSocketChannel_h
 
-#include "nsIWebSocketProtocol.h"
 #include "nsIURI.h"
 #include "nsISupports.h"
 #include "nsIInterfaceRequestor.h"
 #include "nsIEventTarget.h"
 #include "nsIStreamListener.h"
 #include "nsIProtocolHandler.h"
 #include "nsISocketTransport.h"
 #include "nsIAsyncInputStream.h"
@@ -66,174 +66,176 @@
 #include "nsDeque.h"
 
 namespace mozilla { namespace net {
 
 class nsPostMessage;
 class nsWSAdmissionManager;
 class nsWSCompression;
 
-class nsWebSocketHandler : public BaseWebSocketChannel,
-                           public nsIHttpUpgradeListener,
-                           public nsIStreamListener,
-                           public nsIInputStreamCallback,
-                           public nsIOutputStreamCallback,
-                           public nsITimerCallback,
-                           public nsIDNSListener,
-                           public nsIInterfaceRequestor,
-                           public nsIChannelEventSink
+class WebSocketChannel : public BaseWebSocketChannel,
+                         public nsIHttpUpgradeListener,
+                         public nsIStreamListener,
+                         public nsIInputStreamCallback,
+                         public nsIOutputStreamCallback,
+                         public nsITimerCallback,
+                         public nsIDNSListener,
+                         public nsIInterfaceRequestor,
+                         public nsIChannelEventSink
 {
 public:
   NS_DECL_ISUPPORTS
   NS_DECL_NSIHTTPUPGRADELISTENER
   NS_DECL_NSIREQUESTOBSERVER
   NS_DECL_NSISTREAMLISTENER
   NS_DECL_NSIINPUTSTREAMCALLBACK
   NS_DECL_NSIOUTPUTSTREAMCALLBACK
   NS_DECL_NSITIMERCALLBACK
   NS_DECL_NSIDNSLISTENER
   NS_DECL_NSIINTERFACEREQUESTOR
   NS_DECL_NSICHANNELEVENTSINK
 
-  // nsIWebSocketProtocol methods BaseWebSocketChannel didn't implement for us
+  // nsIWebSocketChannel methods BaseWebSocketChannel didn't implement for us
   //
   NS_IMETHOD AsyncOpen(nsIURI *aURI,
                        const nsACString &aOrigin,
                        nsIWebSocketListener *aListener,
                        nsISupports *aContext);
   NS_IMETHOD Close();
   NS_IMETHOD SendMsg(const nsACString &aMsg);
   NS_IMETHOD SendBinaryMsg(const nsACString &aMsg);
   NS_IMETHOD GetSecurityInfo(nsISupports **aSecurityInfo);
 
-  nsWebSocketHandler();
+  WebSocketChannel();
   static void Shutdown();
-  
+
   enum {
-      // Non Control Frames
-      kContinuation = 0x0,
-      kText =         0x1,
-      kBinary =       0x2,
+    // Non Control Frames
+    kContinuation = 0x0,
+    kText =         0x1,
+    kBinary =       0x2,
 
-      // Control Frames
-      kClose =        0x8,
-      kPing =         0x9,
-      kPong =         0xA
+    // Control Frames
+    kClose =        0x8,
+    kPing =         0x9,
+    kPong =         0xA
   };
-  
-  const static PRUint32 kControlFrameMask = 0x8;
-  const static PRUint8 kMaskBit           = 0x80;
-  const static PRUint8 kFinalFragBit      = 0x80;
+
+  const static PRUint32 kControlFrameMask   = 0x8;
+  const static PRUint8 kMaskBit             = 0x80;
+  const static PRUint8 kFinalFragBit        = 0x80;
 
   // section 7.4.1 defines these
   const static PRUint16 kCloseNormal        = 1000;
   const static PRUint16 kCloseGoingAway     = 1001;
   const static PRUint16 kCloseProtocolError = 1002;
   const static PRUint16 kCloseUnsupported   = 1003;
   const static PRUint16 kCloseTooLarge      = 1004;
   const static PRUint16 kCloseNoStatus      = 1005;
   const static PRUint16 kCloseAbnormal      = 1006;
 
 protected:
-  virtual ~nsWebSocketHandler();
+  virtual ~WebSocketChannel();
 
 private:
   friend class nsPostMessage;
   friend class nsWSAdmissionManager;
 
   void SendMsgInternal(nsCString *aMsg, PRInt32 datalen);
   void PrimeNewOutgoingMessage();
   void GeneratePong(PRUint8 *payload, PRUint32 len);
   void GeneratePing();
 
   nsresult BeginOpen();
   nsresult HandleExtensions();
   nsresult SetupRequest();
   nsresult ApplyForAdmission();
   nsresult StartWebsocketData();
   PRUint16 ResultToCloseCode(nsresult resultCode);
-  
+
   void StopSession(nsresult reason);
   void AbortSession(nsresult reason);
   void ReleaseSession();
   void CleanupConnection();
 
   void EnsureHdrOut(PRUint32 size);
   void ApplyMask(PRUint32 mask, PRUint8 *data, PRUint64 len);
 
   PRBool   IsPersistentFramePtr();
   nsresult ProcessInput(PRUint8 *buffer, PRUint32 count);
   PRUint32 UpdateReadBuffer(PRUint8 *buffer, PRUint32 count);
 
   class OutboundMessage
   {
   public:
-      OutboundMessage (nsCString *str)
-          : mMsg(str), mIsControl(PR_FALSE), mBinaryLen(-1)
-      { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
+    OutboundMessage (nsCString *str)
+      : mMsg(str), mIsControl(PR_FALSE), mBinaryLen(-1)
+    { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
 
-      OutboundMessage (nsCString *str, PRInt32 dataLen)
-          : mMsg(str), mIsControl(PR_FALSE), mBinaryLen(dataLen)
-      { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
+    OutboundMessage (nsCString *str, PRInt32 dataLen)
+      : mMsg(str), mIsControl(PR_FALSE), mBinaryLen(dataLen)
+    { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
 
-      OutboundMessage ()
-          : mMsg(nsnull), mIsControl(PR_TRUE), mBinaryLen(-1)
-      { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
+    OutboundMessage ()
+      : mMsg(nsnull), mIsControl(PR_TRUE), mBinaryLen(-1)
+    { MOZ_COUNT_CTOR(WebSocketOutboundMessage); }
 
-      ~OutboundMessage()
-      { 
-          MOZ_COUNT_DTOR(WebSocketOutboundMessage);
-          delete mMsg;
-      }
-      
-      PRBool IsControl()  { return mIsControl; }
-      const nsCString *Msg()  { return mMsg; }
-      PRInt32 BinaryLen() { return mBinaryLen; }
-      PRInt32 Length() 
-      { 
-          if (mBinaryLen >= 0)
-              return mBinaryLen;
-          return mMsg ? mMsg->Length() : 0;
-      }
-      PRUint8 *BeginWriting() 
-      { return (PRUint8 *)(mMsg ? mMsg->BeginWriting() : nsnull); }
-      PRUint8 *BeginReading() 
-      { return (PRUint8 *)(mMsg ? mMsg->BeginReading() : nsnull); }
+    ~OutboundMessage()
+    {
+      MOZ_COUNT_DTOR(WebSocketOutboundMessage);
+      delete mMsg;
+    }
+
+    PRBool IsControl()  { return mIsControl; }
+    const nsCString *Msg()  { return mMsg; }
+    PRInt32 BinaryLen() { return mBinaryLen; }
+    PRInt32 Length()
+    {
+      if (mBinaryLen >= 0)
+        return mBinaryLen;
+      return mMsg ? mMsg->Length() : 0;
+    }
+    PRUint8 *BeginWriting() {
+      return (PRUint8 *)(mMsg ? mMsg->BeginWriting() : nsnull);
+    }
+    PRUint8 *BeginReading() {
+      return (PRUint8 *)(mMsg ? mMsg->BeginReading() : nsnull);
+    }
 
   private:
-      nsCString *mMsg;
-      PRBool     mIsControl;
-      PRInt32    mBinaryLen;
+    nsCString *mMsg;
+    PRBool     mIsControl;
+    PRInt32    mBinaryLen;
   };
-  
+
   nsCOMPtr<nsIEventTarget>                 mSocketThread;
   nsCOMPtr<nsIHttpChannelInternal>         mChannel;
   nsCOMPtr<nsIHttpChannel>                 mHttpChannel;
   nsCOMPtr<nsILoadGroup>                   mLoadGroup;
   nsCOMPtr<nsICancelable>                  mDNSRequest;
   nsCOMPtr<nsIAsyncVerifyRedirectCallback> mRedirectCallback;
   nsCOMPtr<nsIRandomGenerator>             mRandomGenerator;
-  
+
   nsCString                       mHashedSecret;
   nsCString                       mAddress;
 
   nsCOMPtr<nsISocketTransport>    mTransport;
   nsCOMPtr<nsIAsyncInputStream>   mSocketIn;
   nsCOMPtr<nsIAsyncOutputStream>  mSocketOut;
 
   nsCOMPtr<nsITimer>              mCloseTimer;
   PRUint32                        mCloseTimeout;  /* milliseconds */
 
   nsCOMPtr<nsITimer>              mOpenTimer;
   PRUint32                        mOpenTimeout;  /* milliseconds */
 
   nsCOMPtr<nsITimer>              mPingTimer;
   PRUint32                        mPingTimeout;  /* milliseconds */
   PRUint32                        mPingResponseTimeout;  /* milliseconds */
-  
+
   nsCOMPtr<nsITimer>              mLingeringCloseTimer;
   const static PRInt32            kLingeringCloseTimeout =   1000;
   const static PRInt32            kLingeringCloseThreshold = 50;
 
   PRUint32                        mMaxConcurrentConnections;
 
   PRUint32                        mRecvdHttpOnStartRequest   : 1;
   PRUint32                        mRecvdHttpUpgradeTransport : 1;
@@ -242,50 +244,50 @@ private:
   PRUint32                        mServerClosed              : 1;
   PRUint32                        mStopped                   : 1;
   PRUint32                        mCalledOnStop              : 1;
   PRUint32                        mPingOutstanding           : 1;
   PRUint32                        mAllowCompression          : 1;
   PRUint32                        mAutoFollowRedirects       : 1;
   PRUint32                        mReleaseOnTransmit         : 1;
   PRUint32                        mTCPClosed                 : 1;
-  
+
   PRInt32                         mMaxMessageSize;
   nsresult                        mStopOnClose;
   PRUint16                        mCloseCode;
 
   // These are for the read buffers
   PRUint8                        *mFramePtr;
   PRUint8                        *mBuffer;
   PRUint8                         mFragmentOpcode;
   PRUint32                        mFragmentAccumulator;
   PRUint32                        mBuffered;
   PRUint32                        mBufferSize;
   nsCOMPtr<nsIStreamListener>     mInflateReader;
   nsCOMPtr<nsIStringInputStream>  mInflateStream;
 
   // These are for the send buffers
   const static PRInt32 kCopyBreak = 1000;
-  
+
   OutboundMessage                *mCurrentOut;
   PRUint32                        mCurrentOutSent;
   nsDeque                         mOutgoingMessages;
   nsDeque                         mOutgoingPingMessages;
   nsDeque                         mOutgoingPongMessages;
   PRUint32                        mHdrOutToSend;
   PRUint8                        *mHdrOut;
   PRUint8                         mOutHeader[kCopyBreak + 16];
   nsWSCompression                *mCompressor;
   PRUint32                        mDynamicOutputSize;
   PRUint8                        *mDynamicOutput;
 };
 
-class nsWebSocketSSLHandler : public nsWebSocketHandler
+class WebSocketSSLChannel : public WebSocketChannel
 {
 public:
-    nsWebSocketSSLHandler() { BaseWebSocketChannel::mEncrypted = PR_TRUE; }
+    WebSocketSSLChannel() { BaseWebSocketChannel::mEncrypted = PR_TRUE; }
 protected:
-    virtual ~nsWebSocketSSLHandler() {}
+    virtual ~WebSocketSSLChannel() {}
 };
 
 }} // namespace mozilla::net
 
-#endif // mozilla_net_nsWebSocketHandler_h
+#endif // mozilla_net_WebSocketChannel_h
diff --git a/netwerk/protocol/websocket/WebSocketChannelChild.cpp b/netwerk/protocol/websocket/WebSocketChannelChild.cpp
--- a/netwerk/protocol/websocket/WebSocketChannelChild.cpp
+++ b/netwerk/protocol/websocket/WebSocketChannelChild.cpp
@@ -64,23 +64,23 @@ NS_IMETHODIMP_(nsrefcnt) WebSocketChanne
     mRefCnt = 1; /* stabilize */
     delete this;
     return 0;
   }
   return mRefCnt;
 }
 
 NS_INTERFACE_MAP_BEGIN(WebSocketChannelChild)
-  NS_INTERFACE_MAP_ENTRY(nsIWebSocketProtocol)
+  NS_INTERFACE_MAP_ENTRY(nsIWebSocketChannel)
   NS_INTERFACE_MAP_ENTRY(nsIProtocolHandler)
-  NS_INTERFACE_MAP_ENTRY_AMBIGUOUS(nsISupports, nsIWebSocketProtocol)
+  NS_INTERFACE_MAP_ENTRY_AMBIGUOUS(nsISupports, nsIWebSocketChannel)
 NS_INTERFACE_MAP_END
 
 WebSocketChannelChild::WebSocketChannelChild(bool aSecure)
-: mEventQ(static_cast<nsIWebSocketProtocol*>(this))
+: mEventQ(static_cast<nsIWebSocketChannel*>(this))
 , mIPCOpen(false)
 , mCancelled(false)
 {
   LOG(("WebSocketChannelChild::WebSocketChannelChild() %p\n", this));
   BaseWebSocketChannel::mEncrypted = aSecure;
 }
 
 WebSocketChannelChild::~WebSocketChannelChild()
diff --git a/netwerk/protocol/websocket/WebSocketChannelChild.h b/netwerk/protocol/websocket/WebSocketChannelChild.h
--- a/netwerk/protocol/websocket/WebSocketChannelChild.h
+++ b/netwerk/protocol/websocket/WebSocketChannelChild.h
@@ -53,17 +53,17 @@ class WebSocketChannelChild : public Bas
                               public PWebSocketChild
 {
  public:
   WebSocketChannelChild(bool aSecure);
   ~WebSocketChannelChild();
 
   NS_DECL_ISUPPORTS
 
-  // nsIWebSocketProtocol methods BaseWebSocketChannel didn't implement for us
+  // nsIWebSocketChannel methods BaseWebSocketChannel didn't implement for us
   //
   NS_SCRIPTABLE NS_IMETHOD AsyncOpen(nsIURI *aURI,
                                      const nsACString &aOrigin,
                                      nsIWebSocketListener *aListener,
                                      nsISupports *aContext);
   NS_SCRIPTABLE NS_IMETHOD Close();
   NS_SCRIPTABLE NS_IMETHOD SendMsg(const nsACString &aMsg);
   NS_SCRIPTABLE NS_IMETHOD SendBinaryMsg(const nsACString &aMsg);
diff --git a/netwerk/protocol/websocket/WebSocketChannelParent.h b/netwerk/protocol/websocket/WebSocketChannelParent.h
--- a/netwerk/protocol/websocket/WebSocketChannelParent.h
+++ b/netwerk/protocol/websocket/WebSocketChannelParent.h
@@ -36,17 +36,18 @@
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
 #ifndef mozilla_net_WebSocketChannelParent_h
 #define mozilla_net_WebSocketChannelParent_h
 
 #include "mozilla/net/PWebSocketParent.h"
-#include "mozilla/net/nsWebSocketHandler.h"
+#include "nsIWebSocketListener.h"
+#include "nsIWebSocketChannel.h"
 #include "nsCOMPtr.h"
 #include "nsString.h"
 
 class nsIAuthPromptProvider;
 
 namespace mozilla {
 namespace net {
 
@@ -70,16 +71,16 @@ class WebSocketChannelParent : public PW
   bool RecvSendMsg(const nsCString& aMsg);
   bool RecvSendBinaryMsg(const nsCString& aMsg);
   bool RecvDeleteSelf();
   bool CancelEarly();
 
   void ActorDestroy(ActorDestroyReason why);
 
   nsCOMPtr<nsIAuthPromptProvider> mAuthProvider;
-  nsCOMPtr<nsIWebSocketProtocol> mChannel;
+  nsCOMPtr<nsIWebSocketChannel> mChannel;
   bool mIPCOpen;
 };
 
 } // namespace net
 } // namespace mozilla
 
 #endif // mozilla_net_WebSocketChannelParent_h
diff --git a/netwerk/protocol/websocket/nsIWebSocketProtocol.idl b/netwerk/protocol/websocket/nsIWebSocketChannel.idl
rename from netwerk/protocol/websocket/nsIWebSocketProtocol.idl
rename to netwerk/protocol/websocket/nsIWebSocketChannel.idl
--- a/netwerk/protocol/websocket/nsIWebSocketProtocol.idl
+++ b/netwerk/protocol/websocket/nsIWebSocketChannel.idl
@@ -1,9 +1,10 @@
 /* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
+/* vim: set sw=4 ts=4 et tw=80 : */
 /* ***** BEGIN LICENSE BLOCK *****
  * Version: MPL 1.1/GPL 2.0/LGPL 2.1
  *
  * The contents of this file are subject to the Mozilla Public License Version
  * 1.1 (the "License"); you may not use this file except in compliance with
  * the License. You may obtain a copy of the License at
  * http://www.mozilla.org/MPL/
  *
@@ -33,89 +34,23 @@
  * and other provisions required by the GPL or the LGPL. If you do not delete
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
 interface nsIURI;
 interface nsIInterfaceRequestor;
-interface nsIRunnable;
 interface nsILoadGroup;
+interface nsIWebSocketListener;
 
 #include "nsISupports.idl"
 
-/**
- * nsIWebSocketListener
- */
-[scriptable, uuid(b0c27050-31e9-42e5-bc59-499d54b52f99)]
-interface nsIWebSocketListener : nsISupports
-{
-    /**
-     * Called to signify the establishment of the message stream.
-     * Any listener that receives onStart will also receive OnStop.
-     *
-     * @param aContext user defined context
-     */
-    void onStart(in nsISupports aContext);
-
-    /**
-     * Called to signify the completion of the message stream.
-     * OnStop is the final notification the listener will receive and it
-     * completes the WebSocket connection. This event can be received in error
-     * cases even if nsIWebSocketProtocol::Close() has not been called.
-     *
-     * @param aContext user defined context
-     * @param aStatusCode reason for stopping (NS_OK if completed successfully)
-     */
-    void onStop(in nsISupports aContext,
-                in nsresult aStatusCode);
-
-    /**
-     * Called to deliver text message.
-     *
-     * @param aContext user defined context
-     * @param aMsg the message data
-     */
-    void onMessageAvailable(in nsISupports aContext,
-                            in AUTF8String aMsg);
-
-    /**
-     * Called to deliver binary message.
-     *
-     * @param aContext user defined context
-     * @param aMsg the message data
-     */
-    void onBinaryMessageAvailable(in nsISupports aContext,
-                                  in ACString aMsg);
-
-    /**
-     * Called to acknowledge message sent via sendMsg() or sendBinaryMsg.
-     *
-     * @param aContext user defined context
-     * @param aSize number of bytes placed in OS send buffer
-     */
-    void onAcknowledge(in nsISupports aContext, in PRUint32 aSize);
-
-    /**
-     * Called to inform receipt of WebSocket Close message from server.
-     * In the case of errors onStop() can be called without ever
-     * receiving server close.
-     *
-     * No additional messages through onMessageAvailable(),
-     * onBinaryMessageAvailable() or onAcknowledge() will be delievered
-     * to the listener after onServerClose(), though outgoing messages can still
-     * be sent through the nsIWebSocketProtocol connection.
-     */
-    void onServerClose(in nsISupports aContext);
-    
-};
-
-[scriptable, uuid(dc01db59-a513-4c90-824b-085cce06c0aa)]
-interface nsIWebSocketProtocol : nsISupports
+[scriptable, uuid(398a2460-a46d-11e0-8264-0800200c9a66)]
+interface nsIWebSocketChannel : nsISupports
 {
     /**
      * The original URI used to construct the protocol connection. This is used
      * in the case of a redirect or URI "resolution" (e.g. resolving a
      * resource: URI to a file: URI) so that the original pre-redirect
      * URI can still be obtained.  This is never null.
      */
     readonly attribute nsIURI originalURI;
diff --git a/netwerk/protocol/websocket/nsIWebSocketProtocol.idl b/netwerk/protocol/websocket/nsIWebSocketListener.idl
copy from netwerk/protocol/websocket/nsIWebSocketProtocol.idl
copy to netwerk/protocol/websocket/nsIWebSocketListener.idl
--- a/netwerk/protocol/websocket/nsIWebSocketProtocol.idl
+++ b/netwerk/protocol/websocket/nsIWebSocketListener.idl
@@ -1,9 +1,10 @@
 /* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
+/* vim: set sw=4 ts=4 et tw=80 : */
 /* ***** BEGIN LICENSE BLOCK *****
  * Version: MPL 1.1/GPL 2.0/LGPL 2.1
  *
  * The contents of this file are subject to the Mozilla Public License Version
  * 1.1 (the "License"); you may not use this file except in compliance with
  * the License. You may obtain a copy of the License at
  * http://www.mozilla.org/MPL/
  *
@@ -31,42 +32,38 @@
  * use your version of this file under the terms of the MPL, indicate your
  * decision by deleting the provisions above and replace them with the notice
  * and other provisions required by the GPL or the LGPL. If you do not delete
  * the provisions above, a recipient may use your version of this file under
  * the terms of any one of the MPL, the GPL or the LGPL.
  *
  * ***** END LICENSE BLOCK ***** */
 
-interface nsIURI;
-interface nsIInterfaceRequestor;
-interface nsIRunnable;
-interface nsILoadGroup;
-
 #include "nsISupports.idl"
 
 /**
- * nsIWebSocketListener
+ * nsIWebSocketListener: passed to nsIWebSocketChannel::AsyncOpen. Receives
+ * websocket traffic events as they arrive.
  */
 [scriptable, uuid(b0c27050-31e9-42e5-bc59-499d54b52f99)]
 interface nsIWebSocketListener : nsISupports
 {
     /**
      * Called to signify the establishment of the message stream.
      * Any listener that receives onStart will also receive OnStop.
      *
      * @param aContext user defined context
      */
     void onStart(in nsISupports aContext);
 
     /**
      * Called to signify the completion of the message stream.
      * OnStop is the final notification the listener will receive and it
      * completes the WebSocket connection. This event can be received in error
-     * cases even if nsIWebSocketProtocol::Close() has not been called.
+     * cases even if nsIWebSocketChannel::Close() has not been called.
      *
      * @param aContext user defined context
      * @param aStatusCode reason for stopping (NS_OK if completed successfully)
      */
     void onStop(in nsISupports aContext,
                 in nsresult aStatusCode);
 
     /**
@@ -98,93 +95,15 @@ interface nsIWebSocketListener : nsISupp
     /**
      * Called to inform receipt of WebSocket Close message from server.
      * In the case of errors onStop() can be called without ever
      * receiving server close.
      *
      * No additional messages through onMessageAvailable(),
      * onBinaryMessageAvailable() or onAcknowledge() will be delievered
      * to the listener after onServerClose(), though outgoing messages can still
-     * be sent through the nsIWebSocketProtocol connection.
+     * be sent through the nsIWebSocketChannel connection.
      */
     void onServerClose(in nsISupports aContext);
     
 };
 
-[scriptable, uuid(dc01db59-a513-4c90-824b-085cce06c0aa)]
-interface nsIWebSocketProtocol : nsISupports
-{
-    /**
-     * The original URI used to construct the protocol connection. This is used
-     * in the case of a redirect or URI "resolution" (e.g. resolving a
-     * resource: URI to a file: URI) so that the original pre-redirect
-     * URI can still be obtained.  This is never null.
-     */
-    readonly attribute nsIURI originalURI;
 
-    /**
-     * The readonly URI corresponding to the protocol connection after any
-     * redirections are completed.
-     */
-    readonly attribute nsIURI URI;
-
-    /**
-     * The notification callbacks for authorization, etc..
-     */
-    attribute nsIInterfaceRequestor notificationCallbacks;
-
-    /**
-     * Transport-level security information (if any)
-     */
-    readonly attribute nsISupports securityInfo;
-
-    /**
-     * The load group of the websockets code.
-     */
-    attribute nsILoadGroup loadGroup;
-
-    /**
-     * Sec-Websocket-Protocol value
-     */
-    attribute ACString protocol;
-
-    /**
-     * Asynchronously open the websocket connection.  Received messages are fed
-     * to the socket listener as they arrive.  The socket listener's methods
-     * are called on the thread that calls asyncOpen and are not called until
-     * after asyncOpen returns.  If asyncOpen returns successfully, the
-     * protocol implementation promises to call at least onStart and onStop of
-     * the listener.
-     *
-     * NOTE: Implementations should throw NS_ERROR_ALREADY_OPENED if the
-     * websocket connection is reopened.
-     *
-     * @param aURI the uri of the websocket protocol - may be redirected
-     * @param aOrigin the uri of the originating resource
-     * @param aListener the nsIWebSocketListener implementation
-     * @param aContext an opaque parameter forwarded to aListener's methods
-     */
-    void asyncOpen(in nsIURI aURI,
-                   in ACString aOrigin,
-                   in nsIWebSocketListener aListener,
-                   in nsISupports aContext);
-
-    /*
-     * Close the websocket connection for writing - no more calls to sendMsg
-     * or sendBinaryMsg should be made after calling this. The listener object
-     * may receive more messages if a server close has not yet been received.
-     */
-    void close();
-    
-    /**
-     * Use to send text message down the connection to WebSocket peer.
-     *
-     * @param aMsg the utf8 string to send
-     */
-    void sendMsg(in AUTF8String aMsg);
-
-    /**
-     * Use to send binary message down the connection to WebSocket peer.
-     *
-     * @param aMsg the data to send
-     */
-    void sendBinaryMsg(in ACString aMsg);
-};
'''


# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\\SQLEXPRESS;' \
           'DATABASE=ResearchDatasets;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

Get_Records_To_Process_Query = '''
    WITH Q1 AS (
        SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num
            ,Hash_Id
            ,Bug_Ids
            ,Commit_Link
            ,Is_Done_Parent_Child_Hashes
        FROM Bugzilla_Mozilla_ShortLog
        WHERE (Backed_Out_By IS NULL OR Backed_Out_By = '')
            AND (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
            AND Is_Backed_Out_Commit = '0'
    )
    SELECT Row_Num
        ,Hash_Id
        ,Bug_Ids
        ,Commit_Link
        ,Is_Done_Parent_Child_Hashes
    FROM Q1
    WHERE Is_Done_Parent_Child_Hashes = 0 -- Include records have not been processed.
        AND Row_Num BETWEEN ? AND ?
'''

save_changeset_info_query = '''
    INSERT INTO [dbo].[Bugzilla_Mozilla_Changeset_Parent_Child_Hashes]
        ([Changeset_Hash]
        ,[Changeset_Datetime]
        ,[Bug_Ids]
        ,[Parent_Hash]
        ,[Child_Hash]
        ,[File_Names]
        ,[Inserted_On])
    VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
'''

def get_records_to_process(start_row, end_row):
    global conn_str, Get_Records_To_Process_Query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(Get_Records_To_Process_Query, (start_row, end_row))
            rows = cursor.fetchall()
            return rows
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
            exit()

        finally:
            # Close the cursor and connection if they are not None
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("\nFailed after maximum retry attempts due to deadlock.")
        exit()

def is_resolved_bug(bug_id):
    global conn_str, Get_Records_To_Process_Query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(f"SELECT [resolution] from Bugzilla WHERE id = ?", (bug_id))
            queryResult = cursor.fetchone() # fetch one is enough because id is unique.

            # If query yields no data or the resolution is null or not 'FIXED', return false. Otherwise, return true
            if not queryResult or queryResult[0] == None or queryResult[0] != 'FIXED':
                return False
            return True
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - is_resolved_bug({bug_id}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - is_resolved_bug({bug_id}): {e}.")
            exit()

        finally:
            # Close the cursor and connection if they are not None
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("\nFailed after maximum retry attempts due to deadlock.")
        exit()

def obtain_changeset_info(Commit_Link):
    base_url = f"https://hg.mozilla.org"
    request_url = base_url + str(Commit_Link)
    attempt_number = 1
    max_attempt = 5

    try:
        while attempt_number <= max_attempt:
            response = requests.get(request_url)
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                print("Failed with 429 code")
                print("Sleep for 10s and retry...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
            else:
                print(f"Request has status code other than 200. Request url: {request_url}.")
                exit() # if code status is not 200 or 429. It should require human interaction.
            
            if attempt_number == max_attempt:
                print(f"Failed too many request attempts. Status code: {response.status_code}. Exit program.")
                return None
            
        content = response.text

        # Extract Changeset_Datetime
        datetime_match = re.search(r"# Date (\d+ [-+]\d+)", content)
        Changeset_Datetime = datetime_match.group(1) if datetime_match else None

        # Extract parent hashes
        parent_hashes = " | ".join(re.findall(r"# Parent\s+([0-9a-f]+)", content))

        # Extract file changes
        file_changes = []
        diff_blocks = content.split("\ndiff --git ")
        
        for block in diff_blocks[1:]:  # Skip the first block as it does not start with 'diff --git'
            lines = block.splitlines()
            diff_line = lines[0]
            if lines[1].startswith("---"):
                triple_neg_file_name = lines[1].split(" ", 1)[1]
                triple_pos_file_name = lines[2].split(" ", 1)[1]
                file_status = ""
            elif lines[1].startswith("deleted file mode"):
                triple_neg_file_name = lines[2].split(" ", 1)[1]
                triple_pos_file_name = lines[3].split(" ", 1)[1]
                file_status = "deleted"
            elif lines[1].startswith("rename from"):
                if "---" in lines[3] and "+++" in lines[4]:
                    triple_neg_file_name = lines[3].split(" ", 1)[1]
                    triple_pos_file_name = lines[4].split(" ", 1)[1]
                    file_status = "renamed_modified"
                else:
                    triple_neg_file_name = lines[1].split(" ", 1)[1]
                    triple_pos_file_name = lines[2].split(" ", 1)[1]
                    file_status = "renamed"
            elif lines[1].startswith("new file mode"):
                triple_neg_file_name = lines[2].split(" ", 1)[1]
                triple_pos_file_name = lines[3].split(" ", 1)[1]
                file_status = "new"
            elif lines[1].startswith("copy from"):
                if "---" in lines[3] and "+++" in lines[4]:
                    triple_neg_file_name = lines[3].split(" ", 1)[1]
                    triple_pos_file_name = lines[4].split(" ", 1)[1]
                    file_status = "copied"
                else:
                    triple_neg_file_name = lines[1].split(" ", 1)[1]
                    triple_pos_file_name = lines[2].split(" ", 1)[1]
                    file_status = "copied"
            else:
                continue

            file_changes.append({
                "triple_neg_file_name": triple_neg_file_name,
                "triple_pos_file_name": triple_pos_file_name,
                "file_status": file_status
            })

        return {
            "Changeset_Datetime": Changeset_Datetime,
            "parent_hashes": parent_hashes,
            "file_changes": file_changes
        }

    except Exception as e:
        print(f"Error: {e}")
        exit()
        
if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('arg_1', type=int, help='Argument 1')
    # parser.add_argument('arg_2', type=int, help='Argument 2')
    # args = parser.parse_args()
    # start_row = args.arg_1
    # end_row = args.arg_2
    start_row = 4399
    end_row = 4400

    list_of_records = get_records_to_process(start_row, end_row)
    record_count = len(list_of_records)

    for record in list_of_records:
        Row_Num, changeset_hash_Id, Bug_Ids, Commit_Link, Is_Done_Parent_Child_Hashes = record

        print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Process changeset {changeset_hash_Id}...", end="", flush=True)

        # Iterate through 'Bug_Ids' and check if any of them are 'resolved' bugs. If not, no need to process further
        list_of_bug_id = Bug_Ids.split(" | ")
        is_skipped = True
        for bug_id in list_of_bug_id:
            is_resolved = is_resolved_bug(bug_id)
            # If at least one of the bug in the changeset is 'resolved', then we will process this changeset
            if is_resolved == True:
                is_skipped = False
                break

        if is_skipped == True:
            print("Skipped (Bugs Not 'Resolved')")
            continue

        
        data_tuple = obtain_changeset_info(Commit_Link)

        print("Done")
        record_count -= 1

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")
#test chanaged