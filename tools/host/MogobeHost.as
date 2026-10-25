package {
    import flash.display.BitmapData;
    import flash.display.Bitmap;
    import flash.utils.ByteArray;
    import flash.utils.Dictionary;
    import flash.media.SoundMixer;
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.Loader;
    import flash.display.MovieClip;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.utils.getTimer;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.events.IOErrorEvent;
    import flash.events.SecurityErrorEvent;
    import flash.events.KeyboardEvent;
    import flash.external.ExternalInterface;
    import flash.net.URLRequest;
    import flash.geom.Rectangle;
    import flash.geom.Point;
    import flash.geom.Matrix;
    import flash.text.TextField;
    import flash.text.StaticText;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.text.TextFormatAlign;
    import flash.system.ApplicationDomain;
    import flash.system.LoaderContext;
    import flash.utils.getQualifiedClassName;

    public dynamic class MogobeHost extends MovieClip {
        private var gameLoader:Loader;
        private var originalPreloader:Loader;
        private var scoreSignsShown:int = 0;
        private var lastScoreSign:String = "";
        private var profileIconLoader:Loader;
        private var profileIconDomain:ApplicationDomain;
        private var mapAssetsLoader:Loader;
        private var mapAssetsDomain:ApplicationDomain;
        private var mapAssetsError:String = "";
        private var mapAssetsLoads:int = 0;
        private var lastState:String = "";
        private var hasLobby:Boolean;
        private var mainClip:DisplayObjectContainer;
        private var cookieManager:Object;
        private var currentLogin:DisplayObjectContainer;
        private var hookedLogin:DisplayObjectContainer;
        private var laidOutLogin:DisplayObjectContainer;
        private var loginKind:String = "";
        private var lastLoginView:String = "";
        private var rememberedNames:String = "";
        private var registrationUser:String = "";
        private var registrationPending:Boolean = false;
        private var displayNames:Object = {};
        private var popupLoader:Loader;
        private var popupWindow:MovieClip;
        private var popupText:TextField;
        private var popupFont:Object;
        private var popupBackground:Sprite;
        private var popupBackgroundBounds:Rectangle;
        private var popupTextBounds:Rectangle;
        private var popupTextFormat:TextFormat;
        private var popupButtonY:Number;

        private var worldLoginInfo:Object;
        private var worldStarting:Boolean = false;
        private var hookedServers:DisplayObjectContainer;
        private var serversPresence:Array = [];
        private var worldAvatar:DisplayObject;
        private var socialState:Object = {};
        private var socialPopupStack:Array = [];
        private var pendingMutes:Object = {};
        private var muteSequence:int = 0;
        private var friendHover:MovieClip;
        private var friendHoverText:String = "";
        private var friendHoverTime:int;
        private var friendTooltip:Sprite;

        public function MogobeHost() {
            super();
            scrollRect = new Rectangle(0,0,768,480);
            if (loaderInfo.parameters.popupMode == "true") {
                loadRegistrationPopup();
                return;
            }
            gameLoader = new Loader();
            gameLoader.addEventListener(Event.ADDED, originalDisplayAdded, true, 200);
            gameLoader.addEventListener(KeyboardEvent.KEY_DOWN, worldChatKey, true, 100);
            gameLoader.addEventListener(MouseEvent.CLICK, worldChatClick, true, 100);
            gameLoader.addEventListener(MouseEvent.CLICK, socialClick, true, 200);
            gameLoader.addEventListener(MouseEvent.CLICK, avatarCameraClick, true, 300);
            gameLoader.addEventListener(MouseEvent.MOUSE_OVER, friendMouseOver, true, 200);
            gameLoader.addEventListener(MouseEvent.MOUSE_OUT, friendMouseOut, true, 200);
            gameLoader.addEventListener(MouseEvent.MOUSE_WHEEL, shopCategoryWheel, true, 200);
            addChild(gameLoader);
            originalPreloader = new Loader();
            originalPreloader.mouseEnabled = false;
            originalPreloader.mouseChildren = false;
            addChild(originalPreloader);
            addEventListener(Event.ENTER_FRAME, inspectScene);
            // Timeline frames and the original controllers can recreate text
            // after ENTER_FRAME. Repair the completed frame before it is drawn.
            addEventListener(Event.EXIT_FRAME, finishOriginalFrame);
            addEventListener(Event.RENDER, finishOriginalRender);
            ExternalInterface.addCallback("showOriginalLoading", showOriginalLoading);
            ExternalInterface.addCallback("refreshRememberedState", refreshRememberedState);
            ExternalInterface.addCallback("getLoginControlBounds", getLoginControlBounds);
            ExternalInterface.addCallback("getSavedAvatarInfo", getSavedAvatarInfo);
            ExternalInterface.addCallback("openMinigame",openMinigame);
            ExternalInterface.addCallback("closeMinigame",closeMinigame);
            ExternalInterface.addCallback("showMinigameResult",showMinigameResult);
            ExternalInterface.addCallback("getMinigameInfo",getMinigameInfo);
            ExternalInterface.addCallback("closeMinigameHelp",closeMiniHelp);
            addEventListener(KeyboardEvent.KEY_DOWN,miniKey,true,300);
            ExternalInterface.addCallback("finishRegistrationLogin", finishRegistrationLogin);
            ExternalInterface.addCallback("beginWorld", beginWorld);
            ExternalInterface.addCallback("getWorldAvatar", getWorldAvatar);
            ExternalInterface.addCallback("getWorldAvatars", getWorldAvatars);
            ExternalInterface.addCallback("setServerPresence", setServerPresence);
            ExternalInterface.addCallback("getServerInfo", getServerInfo);
            ExternalInterface.addCallback("getProfileInfo", getProfileInfo);
            ExternalInterface.addCallback("getInventoryInfo", getInventoryInfo);
            ExternalInterface.addCallback("setProfileProgress", setProfileProgress);
            ExternalInterface.addCallback("getExperienceInfo", getExperienceInfo);
            ExternalInterface.addCallback("openOriginalShop",openOriginalShop);
            ExternalInterface.addCallback("refreshOriginalShop",refreshOriginalShop);
            ExternalInterface.addCallback("finishShopPurchase",finishShopPurchase);
            ExternalInterface.addCallback("closeOriginalShop",closeOriginalShop);
            ExternalInterface.addCallback("getShopInfo",getShopInfo);
            ExternalInterface.addCallback("setWorldShopPoints",setWorldShopPoints);
            ExternalInterface.addCallback("getWorldShopPoints",getWorldShopPoints);
            ExternalInterface.addCallback("getWorldShopState",getWorldShopState);
            ExternalInterface.addCallback("getWorldPanelInfo", getWorldPanelInfo);
            ExternalInterface.addCallback("getRoomAudioInfo", getRoomAudioInfo);
            ExternalInterface.addCallback("getWorldMapInfo", getWorldMapInfo);
            ExternalInterface.addCallback("addChatHistory", addChatHistory);
            ExternalInterface.addCallback("getChatHistoryInfo", getChatHistoryInfo);
            ExternalInterface.addCallback("getChatMenuItems", getChatMenuItems);
            ExternalInterface.addCallback("setSocialState", setSocialState);
            ExternalInterface.addCallback("finishMuteChange", finishMuteChange);
            ExternalInterface.addCallback("getFriendsTooltipInfo", getFriendsTooltipInfo);
            ExternalInterface.addCallback("chooseOriginalServer", chooseOriginalServer);
            ExternalInterface.addCallback("getSocialPopupInfo", getSocialPopupInfo);
            ExternalInterface.addCallback("getSocialRowControlBounds", getSocialRowControlBounds);
            ExternalInterface.addCallback("getWorldEffects", getWorldEffects);
            ExternalInterface.addCallback("getWorldCursor", getWorldCursor);
            ExternalInterface.addCallback("getProfileControlBounds", getProfileControlBounds);
            originalPreloader.contentLoaderInfo.addEventListener(Event.COMPLETE, loadOriginalLogin);
            originalPreloader.load(new URLRequest("/compat/OriginalPreloader.swf"));
            preloadChatHistory();
            preloadWorldMap();
            preloadProfileIcons();
        }

        private function loadRegistrationPopup():void {
            ExternalInterface.addCallback("showMessage", showMessage);
            ExternalInterface.addCallback("getPopupControlBounds", getPopupControlBounds);
            ExternalInterface.addCallback("getMessageInfo", getMessageInfo);
            gameLoader = new Loader();
            gameLoader.contentLoaderInfo.addEventListener(Event.COMPLETE, popupFontsLoaded);
            gameLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, popupLoadFailed);
            gameLoader.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, popupLoadFailed);
            // The unstarted original login supplies its embedded Russian Arial.
            gameLoader.load(new URLRequest("/Swf/Login.swf"), new LoaderContext(false, ApplicationDomain.currentDomain));
        }

        private function popupLoadFailed(event:Event):void {
            ExternalInterface.call("onMogobePopupFailed");
        }

        private function popupFontsLoaded(event:Event):void {
            gameLoader.contentLoaderInfo.removeEventListener(Event.COMPLETE, popupFontsLoaded);
            var fonts:Class = ApplicationDomain.currentDomain.getDefinition("FontClass") as Class;
            popupFont = Object(fonts).getInstance();
            popupLoader = new Loader();
            popupLoader.contentLoaderInfo.addEventListener(Event.COMPLETE, popupGraphicsLoaded);
            popupLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, popupLoadFailed);
            popupLoader.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, popupLoadFailed);
            popupLoader.load(new URLRequest("/Swf/Assets/Popups/RegistrationPopups.swf"), new LoaderContext(false, ApplicationDomain.currentDomain));
        }

        private function popupGraphicsLoaded(event:Event):void {
            var alertClass:Class = ApplicationDomain.currentDomain.getDefinition("mlAlert") as Class;
            popupWindow = new alertClass() as MovieClip;
            popupWindow.stop();
            addChild(popupWindow);
            var bounds:Rectangle = popupWindow.getBounds(popupWindow);
            popupWindow.x = 384 - bounds.x - bounds.width / 2;
            popupWindow.y = 240 - bounds.y - bounds.height / 2;
            // Save the authored message area before FontClass auto-sizes its clone.
            var originalText:TextField = Object(popupWindow).txtMessage as TextField;
            popupTextBounds = new Rectangle(originalText.x,originalText.y,originalText.width,originalText.height);
            popupText = popupFont.addText(originalText, "", 420) as TextField;
            Object(popupWindow).txtMessage = popupText;
            popupTextFormat = popupText.defaultTextFormat;
            // Reuse the original frame artwork, with fixed corners for a taller help panel.
            var artwork:DisplayObject = popupWindow.getChildAt(0);
            popupBackgroundBounds = artwork.getBounds(popupWindow);
            popupWindow.removeChild(artwork);
            popupBackground = new Sprite();
            popupBackground.addChild(artwork);
            popupBackground.scale9Grid = new Rectangle(popupBackgroundBounds.x+12,popupBackgroundBounds.y+12,popupBackgroundBounds.width-24,popupBackgroundBounds.height-24);
            popupWindow.addChildAt(popupBackground,0);
            popupButtonY = Object(popupWindow).btnConfirm.y;
            var button:MovieClip = Object(popupWindow).btnConfirm as MovieClip;
            button.gotoAndStop("OUT");
            button.buttonMode = true;
            button.mouseChildren = false;
            button.addEventListener(MouseEvent.MOUSE_OVER, popupButtonOver);
            button.addEventListener(MouseEvent.MOUSE_OUT, popupButtonOut);
            button.addEventListener(MouseEvent.CLICK, closePopup);
            stage.addEventListener(KeyboardEvent.KEY_DOWN, popupKeyDown);
            ExternalInterface.call("onMogobePopupReady");
        }

        private function popupButtonOver(event:MouseEvent):void {
            MovieClip(event.currentTarget).gotoAndStop("OVER");
        }

        private function popupButtonOut(event:MouseEvent):void {
            MovieClip(event.currentTarget).gotoAndStop("OUT");
        }

        private function popupKeyDown(event:KeyboardEvent):void {
            if (event.keyCode == 13 || event.keyCode == 27) closePopup(event);
        }

        private function closePopup(event:Event):void {
            ExternalInterface.call("onMogobePopupClosed");
        }

        public function showMessage(message:String, commands:Boolean = false):void {
            if (popupText == null) return;
            var format:TextFormat = new TextFormat(popupTextFormat.font,commands ? 14 : popupTextFormat.size,popupTextFormat.color);
            format.align = commands ? TextFormatAlign.LEFT : TextFormatAlign.CENTER;
            format.leading = commands ? 3 : popupTextFormat.leading;
            popupText.autoSize = "left";
            popupText.defaultTextFormat = format;
            popupText.width = popupTextBounds.width-(commands ? 16 : 0);
            popupText.text = message;
            popupText.setTextFormat(format);
            popupText.x = popupTextBounds.x;
            popupText.y = popupTextBounds.y;
            var extra:Number = Math.max(0,popupText.height-popupTextBounds.height)+(commands ? 8 : 0);
            if (!commands) popupText.y += (popupTextBounds.height+extra-popupText.height)/2;
            popupBackground.height = popupBackgroundBounds.height+extra;
            popupBackground.y += popupBackgroundBounds.y-popupBackground.getBounds(popupWindow).y;
            Object(popupWindow).btnConfirm.y = popupButtonY+extra;
            var bounds:Rectangle = popupWindow.getBounds(popupWindow);
            popupWindow.x = 384-bounds.x-bounds.width/2;
            popupWindow.y = 240-bounds.y-bounds.height/2;
            popupWindow.focusRect = false;
            stage.focus = popupWindow;
        }

        public function getMessageInfo():Object {
            if(popupText==null)return null;
            var text:Rectangle=popupText.getBounds(this);
            var button:Rectangle=Object(popupWindow).btnConfirm.getBounds(this);
            var panel:Rectangle=popupWindow.getBounds(this);
            return {text:popupText.text,textBottom:text.bottom,textRight:text.right,buttonTop:button.top,buttonLeft:button.left,lines:popupText.numLines,
                align:popupText.getTextFormat().align,centerOffsetX:popupText.x+popupText.width/2-popupTextBounds.x-popupTextBounds.width/2,
                centerOffsetY:popupText.y+popupText.height/2-popupTextBounds.y-(popupTextBounds.height+Math.max(0,popupText.height-popupTextBounds.height))/2,
                panel:{x:panel.x,y:panel.y,width:panel.width,height:panel.height}};
        }

        public function getPopupControlBounds(name:String):Object {
            var control:DisplayObject = findNamed(popupWindow, name, 0);
            if (control == null) return null;
            var bounds:Rectangle = control.getBounds(this);
            return {x:bounds.x, y:bounds.y, width:bounds.width, height:bounds.height};
        }

        private function loadOriginalLogin(event:Event):void {
            originalPreloader.contentLoaderInfo.removeEventListener(Event.COMPLETE, loadOriginalLogin);
            gameLoader.contentLoaderInfo.addEventListener(Event.COMPLETE, startOriginalLogin);
            gameLoader.load(new URLRequest("/Swf/Login.swf"), new LoaderContext(false, ApplicationDomain.currentDomain));
        }

        public function showOriginalLoading(visible:Boolean):void {
            originalPreloader.visible = visible;
            gameLoader.visible = !visible && miniLayer == null;
            gameLoader.mouseChildren = !visible;
            gameLoader.mouseEnabled = !visible;
        }

        private function startOriginalLogin(event:Event):void {
            gameLoader.contentLoaderInfo.removeEventListener(Event.COMPLETE, startOriginalLogin);
            var cookiesClass:Class = gameLoader.contentLoaderInfo.applicationDomain.getDefinition("worlds4u.model.CookiesDataManager") as Class;
            cookieManager = Object(cookiesClass).getInstance();
            seedRemembered(ExternalInterface.call("getRememberedMogobes") as Array);
            var registered:Object = ExternalInterface.call("getRegistrationMogobe");
            if (registered != null && String(registered) != "") {
                registrationUser = String(registered);
                registrationPending = true;
            }
            Object(gameLoader.content).init();
        }

        public function finishRegistrationLogin(success:Boolean):void {
            if (!success) registrationPending = false;
        }

        private function seedRemembered(accounts:Array):void {
            if (accounts == null || cookieManager == null) return;
            var data:Object = {userName:"", password:"", saveUserName:true, savePassword:false, lang:5};
            var names:Array = [];
            displayNames = {};
            for (var i:int = 0; i < accounts.length && i < 6; i++) {
                var account:Object = accounts[i];
                displayNames["$" + String(account.username).toLowerCase()] = String(account.username);
                // Original LoginDataManager lowercases names and compares them case-sensitively.
                data["userName" + i] = String(account.username).toLowerCase();
                data["userColour" + i] = account.color_id;
                data["saveData" + i] = true;
                data["savePassword" + i] = Boolean(account.has_session);
                // This is a non-secret marker. Session tokens never enter Flash/JS.
                data["userPassword" + i] = account.has_session ? "__MOGOBE_SAVED_SESSION__" : "";
                data["itemsIdList" + i] = account.item_ids is Array ? account.item_ids.join(",") : "";
                names.push(String(account.username).toLowerCase());
            }
            rememberedNames = names.join("|");
            cookieManager.deleteObject("loginInfo");
            cookieManager.setObject("loginInfo", data);
        }

        public function refreshRememberedState(accounts:Array):void {
            seedRemembered(accounts);
            if (currentLogin == null || loginKind != "saved") return;
            var holder:DisplayObjectContainer = findNamed(currentLogin, "mcBigPreviewHolderInst", 0) as DisplayObjectContainer;
            var password:TextField = findNamed(currentLogin, "txtMultiLoginPassword", 0) as TextField;
            if (holder == null || password == null) return;
            var name:TextField = findNamed(holder, "txtNameSmall", 0) as TextField;
            if (name == null) return;
            for each (var account:Object in accounts) {
                if (String(account.username).toLowerCase() == name.text.toLowerCase() && !account.has_session && password.text == "__MOGOBE_SAVED_SESSION__") {
                    password.text = "";
                }
            }
        }

        private function onLoginRequested(event:Event):void {
            serversPresence = [];
            var info:Object = Object(currentLogin).loginInfo;
            worldLoginInfo = info;
            ExternalInterface.call("onMogobeLoginPreferences", String(info.userName), Boolean(info.saveUserName), Boolean(info.savePassword));
            // Original Login.setCookies runs after success. Never persist its raw password.
            info.savePassword = false;
        }

        private function onWorldSelected(event:Event):void {
            beginWorld();
        }

        public function beginWorld():void {
            if (worldLoginInfo != null) worldLoginInfo.password = "__MOGOBE_CURRENT_SESSION__";
            worldStarting = true;
            showOriginalLoading(true);
        }

        public function getWorldAvatar():Object {
            if (worldAvatar == null) return null;
            return {x:worldAvatar.x, y:worldAvatar.y, visible:worldAvatar.visible, colorId:Object(worldAvatar).Color, action:Object(worldAvatar).currentAction, type:getQualifiedClassName(worldAvatar)};
        }

        public function getWorldAvatars():Array {
            var result:Array = [];
            if (worldAvatar == null || worldAvatar.parent == null) return result;
            var holder:DisplayObjectContainer = worldAvatar.parent;
            for (var i:int = 0; i < holder.numChildren; i++) {
                var avatar:DisplayObject = holder.getChildAt(i);
                var type:String = getQualifiedClassName(avatar);
                if (type != "worlds4u.view.avatar::MyAvatar" && type != "worlds4u.view.avatar::AvatarDocView") continue;
                var balloon:DisplayObject = avatarBalloon(avatar as DisplayObjectContainer);
                var text:String = "";
                if (balloon != null) text = collectText(balloon);
                var clothing:Array=[]; collectOutfitClips(avatar,clothing);
                result.push({clothing:clothing,id:int(avatar.name), x:avatar.x, y:avatar.y, colorId:Object(avatar).Color, action:Object(avatar).currentAction, me:avatar == worldAvatar, speech:text,
                    speechLayout:speechInfo(balloon),
                    balloonCount:avatarBalloonCount(avatar as DisplayObjectContainer),
                    balloonType:balloon == null ? "" : getQualifiedClassName(balloon),
                    balloonLabel:balloon is MovieClip ? MovieClip(balloon).currentLabel : "",
                    balloonChildren:balloon is DisplayObjectContainer ? childTypes(balloon as DisplayObjectContainer) : []});
            }
            return result;
        }

        private var speechBalloons:Array = [];

        private function avatarBalloon(avatar:DisplayObjectContainer):DisplayObject {
            var nativeBalloon:DisplayObject = avatar.getChildByName("speakBallon");
            return nativeBalloon == null ? avatar.getChildByName("mogobeSpeechBalloon") : nativeBalloon;
        }

        private function avatarBalloonCount(avatar:DisplayObjectContainer):int {
            var count:int = 0;
            for (var i:int = 0; i < avatar.numChildren; i++) {
                var child:DisplayObject = avatar.getChildAt(i);
                if (child.name == "speakBallon" || child.name == "mogobeSpeechBalloon") count++;
            }
            return count;
        }

        private function observeSpeechBalloon(view:DisplayObject):void {
            if (view == null || view.name != "speakBallon" || view.parent == null) return;
            var avatar:DisplayObjectContainer = view.parent;
            var type:String = getQualifiedClassName(avatar);
            if (type != "worlds4u.view.avatar::MyAvatar" && type != "worlds4u.view.avatar::AvatarDocView") return;
            // A new message, emotion or spell replaces the previous speech.
            for (var i:int = speechBalloons.length-1; i >= 0; i--) {
                var previous:Object = speechBalloons[i];
                if (previous.avatar == avatar) {
                    if (previous.balloon.parent == avatar) avatar.removeChild(previous.balloon);
                    disposeSpeechSkin(previous);
                    speechBalloons.splice(i,1);
                }
            }
            type = getQualifiedClassName(view);
            if (type != "mlBallon_1" && type != "mlBallon_2" && type != "mlBallon_3") return;
            // The original private timer removes only the child named
            // speakBallon after four seconds. Manage text lifetime separately;
            // emotions and spells retain that original name and timer.
            view.name = "mogobeSpeechBalloon";
            view.visible = false;
            MovieClip(view).mouseEnabled = false;
            MovieClip(view).mouseChildren = false;
            speechBalloons.push({avatar:avatar,balloon:view,x:view.x,y:view.y,ready:false});
        }

        private function speechField(balloon:DisplayObjectContainer):TextField {
            for (var i:int = 0; i < balloon.numChildren; i++) {
                var field:TextField = balloon.getChildAt(i) as TextField;
                if (field != null && field.visible && field.text.length > 0) return field;
            }
            return null;
        }

        private function makeSpeechSkin(original:Shape, source:Rectangle, tail:Number, width:Number, height:Number, entry:Object):Sprite {
            var skin:Sprite = new Sprite();
            skin.name = "mogobeSpeechSkin";
            var sourceX:Array = [source.left,40,source.right-12,source.right];
            var sourceY:Array = [source.top,source.top+4,source.bottom-tail-4,source.bottom];
            var left:Number = source.left;
            var top:Number = source.bottom-height;
            var targetX:Array = [left,40,left+width-12,left+width];
            var targetY:Array = [top,top+4,source.bottom-tail-4,source.bottom];
            var resolution:Number = 2;
            var pixels:BitmapData = new BitmapData(Math.ceil(width*resolution)+2,Math.ceil(height*resolution)+2,true,0);
            // Compose the original vectors in one offscreen surface. Integer
            // clips overlap by one pixel, so fractional avatar/window scaling
            // cannot expose transparent seams between independent textures.
            for (var row:int = 0; row < 3; row++) for (var col:int = 0; col < 3; col++) {
                var sx:Number = (targetX[col+1]-targetX[col])/(sourceX[col+1]-sourceX[col]);
                var sy:Number = (targetY[row+1]-targetY[row])/(sourceY[row+1]-sourceY[row]);
                var placement:Matrix = new Matrix(sx*resolution,0,0,sy*resolution,
                    (targetX[col]-sourceX[col]*sx-left)*resolution+1,
                    (targetY[row]-sourceY[row]*sy-top)*resolution+1);
                var x1:int = Math.max(0,Math.floor((targetX[col]-left)*resolution));
                var y1:int = Math.max(0,Math.floor((targetY[row]-top)*resolution));
                var x2:int = Math.min(pixels.width,Math.ceil((targetX[col+1]-left)*resolution)+2);
                var y2:int = Math.min(pixels.height,Math.ceil((targetY[row+1]-top)*resolution)+2);
                pixels.draw(original,placement,null,null,new Rectangle(x1,y1,x2-x1,y2-y1),true);
            }
            var bitmap:Bitmap = new Bitmap(pixels,"auto",true);
            bitmap.scaleX = bitmap.scaleY = 1/resolution;
            bitmap.x = left-1/resolution; bitmap.y = top-1/resolution;
            skin.addChild(bitmap);
            // Inspect actual rendered pixels at the interior joins, before the
            // live embedded-font TextField is placed above this background.
            var alpha:int = 255;
            var x:int; var y:int;
            for each (var seamX:Number in [40-left,width-12]) {
                x = int(seamX*resolution)+1;
                for (y = 13; y < int((height-tail-6)*resolution)+1; y++)
                    alpha = Math.min(alpha,pixels.getPixel32(x,y)>>>24);
            }
            y = int((height-tail-4)*resolution)+1;
            for (x = 29; x < int((width-14)*resolution)+1; x++)
                alpha = Math.min(alpha,pixels.getPixel32(x,y)>>>24);
            entry.seamAlpha = alpha;
            entry.transparentCorners = ((pixels.getPixel32(0,0)|pixels.getPixel32(pixels.width-1,0)|
                pixels.getPixel32(0,pixels.height-1)|pixels.getPixel32(pixels.width-1,pixels.height-1))>>>24) == 0;
            return skin;
        }

        private function disposeSpeechSkin(entry:Object):void {
            if (entry.skin == null || entry.skin.numChildren == 0) return;
            var bitmap:Bitmap = entry.skin.getChildAt(0) as Bitmap;
            if (bitmap != null && bitmap.bitmapData != null) {
                bitmap.bitmapData.dispose();
                bitmap.bitmapData = null;
            }
        }

        private function prepareSpeech(entry:Object):Boolean {
            var balloon:MovieClip = entry.balloon as MovieClip;
            var field:TextField = speechField(balloon);
            if (field == null) return false; // FontClass replaces the authored sample synchronously.
            var original:Shape;
            for (var i:int = 0; i < balloon.numChildren; i++) {
                if (balloon.getChildAt(i) is Shape) { original = balloon.getChildAt(i) as Shape; break; }
            }
            if (original == null) return false;
            var source:Rectangle = original.getBounds(balloon);
            var type:String = getQualifiedClassName(balloon);
            var tail:Number = type == "mlBallon_1" ? 6 : type == "mlBallon_2" ? 10 : 14;
            var format:TextFormat = field.defaultTextFormat;
            format.align = TextFormatAlign.LEFT;
            format.leftMargin = 0; format.rightMargin = 0; format.indent = 0;
            field.defaultTextFormat = format;
            field.setTextFormat(format);
            field.multiline = true;
            field.wordWrap = false;
            field.autoSize = TextFieldAutoSize.LEFT;
            var paddingX:Number = 12;
            var paddingY:Number = 4;
            var scale:Number = Math.abs(field.scaleX);
            var width:Number = Math.min(220,Math.max(128,Math.ceil((field.textWidth+4)*scale+paddingX*2)));
            field.autoSize = TextFieldAutoSize.NONE;
            field.wordWrap = true;
            field.width = width-paddingX*2;
            field.autoSize = TextFieldAutoSize.LEFT;
            // Find the narrowest column that keeps the current line count.
            // This balances wrapped words instead of leaving one long line
            // followed by a mostly empty row in a needlessly wide bubble.
            var lines:int = field.numLines;
            var low:int = 128-paddingX*2;
            var high:int = Math.ceil(field.width);
            for (var attempt:int = 0; attempt < 8 && low < high; attempt++) {
                var middle:int = (low+high)>>1;
                field.width = middle;
                if (field.numLines > lines) low = middle+1;
                else high = middle;
            }
            field.width = high;
            width = high+paddingX*2;
            // Keep only the actual widest line and the native text gutter.
            var longest:Number = 0;
            for (i = 0; i < field.numLines; i++) longest = Math.max(longest,field.getLineMetrics(i).width*scale);
            width = Math.min(width,Math.max(128,Math.ceil(longest+4*scale+paddingX*2)));
            field.width = width-paddingX*2;
            field.scrollH = 0; field.scrollV = 1;
            var height:Number = Math.ceil(field.height+paddingY*2+tail);
            var skin:Sprite = makeSpeechSkin(original,source,tail,width,height,entry);
            balloon.removeChild(original);
            balloon.addChildAt(skin,0);
            entry.paddingX = paddingX; entry.paddingY = paddingY;
            entry.skin = skin;
            entry.skinRect = new Rectangle(source.left,source.bottom-height,width,height);
            entry.field = field;
            entry.duration = Math.min(20000,Math.max(4000,2000+field.text.length*60));
            entry.expires = getTimer()+entry.duration;
            entry.ready = true;
            balloon.visible = true;
            return true;
        }

        private function speechRect(node:DisplayObject, rect:Rectangle, target:DisplayObject):Rectangle {
            // getBounds on nested scrollRect patches is inconsistent in Ruffle.
            // Map the authored skin rectangle through the actual transforms.
            var a:Point = target.globalToLocal(node.localToGlobal(new Point(rect.left,rect.top)));
            var b:Point = target.globalToLocal(node.localToGlobal(new Point(rect.right,rect.bottom)));
            return new Rectangle(Math.min(a.x,b.x),Math.min(a.y,b.y),Math.abs(b.x-a.x),Math.abs(b.y-a.y));
        }

        private function positionSpeech(entry:Object):void {
            var balloon:MovieClip = entry.balloon as MovieClip;
            var skin:Sprite = entry.skin as Sprite;
            var field:TextField = entry.field as TextField;
            balloon.x = entry.x; balloon.y = entry.y;
            skin.scaleX = 1; skin.x = 0;
            var normal:Rectangle = speechRect(skin,entry.skinRect,this);
            if (normal.right > 760) {
                // Mirror the original skin around its tail, keeping the text
                // readable and the pointer attached to the same avatar point.
                skin.scaleX = -1; skin.x = 49.4;
                var mirrored:Rectangle = speechRect(skin,entry.skinRect,this);
                if (mirrored.left < 8 && 8-mirrored.left > normal.right-760) {
                    skin.scaleX = 1; skin.x = 0;
                }
            }
            var box:Rectangle = speechRect(skin,entry.skinRect,balloon);
            field.x = box.left+entry.paddingX; field.y = box.top+entry.paddingY;
            var screen:Rectangle = speechRect(skin,entry.skinRect,this);
            var dx:Number = screen.left < 8 ? 8-screen.left : screen.right > 760 ? 760-screen.right : 0;
            var dy:Number = screen.top < 8 ? 8-screen.top : 0;
            if (dx != 0 || dy != 0) {
                var origin:Point = entry.avatar.globalToLocal(localToGlobal(new Point(0,0)));
                var shifted:Point = entry.avatar.globalToLocal(localToGlobal(new Point(dx,dy)));
                balloon.x += shifted.x-origin.x;
                balloon.y += shifted.y-origin.y;
            }
        }

        private function updateSpeechBalloons():void {
            // Also catch speech created before an avatar was attached to the
            // world, when its ADDED event could not reach the loader.
            var avatars:DisplayObjectContainer = worldAvatar == null ? null : worldAvatar.parent;
            for (var j:int = 0; avatars != null && j < avatars.numChildren; j++) {
                var avatar:DisplayObjectContainer = avatars.getChildAt(j) as DisplayObjectContainer;
                if (avatar == null) continue;
                var pending:DisplayObject = avatar.getChildByName("speakBallon");
                if (pending != null && getQualifiedClassName(pending).indexOf("mlBallon_") == 0) observeSpeechBalloon(pending);
            }
            for (var i:int = speechBalloons.length-1; i >= 0; i--) {
                var entry:Object = speechBalloons[i];
                if (entry.avatar.stage == null || entry.balloon.parent != entry.avatar) {
                    if (entry.balloon.parent == entry.avatar) entry.avatar.removeChild(entry.balloon);
                    disposeSpeechSkin(entry);
                    speechBalloons.splice(i,1);
                    continue;
                }
                if (!entry.ready && !prepareSpeech(entry)) continue;
                if (getTimer() >= entry.expires) {
                    entry.avatar.removeChild(entry.balloon);
                    disposeSpeechSkin(entry);
                    speechBalloons.splice(i,1);
                } else positionSpeech(entry);
            }
        }

        private function speechInfo(balloon:DisplayObject):Object {
            for each (var entry:Object in speechBalloons) {
                if (entry.balloon != balloon || !entry.ready) continue;
                var bounds:Rectangle = speechRect(entry.skin,entry.skinRect,this);
                var field:TextField = entry.field as TextField;
                var text:Rectangle = speechRect(field,new Rectangle(0,0,field.width/Math.abs(field.scaleX),field.height/Math.abs(field.scaleY)),this);
                var longest:Number = 0;
                for (var i:int = 0; i < field.numLines; i++) longest = Math.max(longest,field.getLineMetrics(i).width*Math.abs(field.scaleX));
                return {localWidth:entry.skinRect.width,localHeight:entry.skinRect.height,
                    fieldWidth:field.width,longestLine:longest,seamAlpha:entry.seamAlpha,
                    transparentCorners:entry.transparentCorners,
                    x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
                    textX:text.x,textY:text.y,textWidth:text.width,textHeight:text.height,
                    contentHeight:entry.field.textHeight,fieldHeight:entry.field.height,
                    lines:entry.field.numLines,maxScrollV:entry.field.maxScrollV,
                    duration:entry.duration,remaining:Math.max(0,entry.expires-getTimer()),
                    mirrored:entry.skin.scaleX < 0};
            }
            return null;
        }

        private function collectServerRows(node:DisplayObject, rows:Array):void {
            if (node == null || !node.visible) return;
            if (getQualifiedClassName(node) == "mlServer") {
                rows.push(node);
                return;
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            for (var i:int = 0; holder != null && i < holder.numChildren; i++) collectServerRows(holder.getChildAt(i),rows);
        }

        public function setServerPresence(servers:Array):void {
            serversPresence = servers;
            updateServerPresence();
        }

        private function updateServerPresence():void {
            if (loginKind != "servers" || hookedServers == null || hookedServers.stage == null) return;
            var rows:Array = [];
            collectServerRows(hookedServers,rows);
            for (var i:int = 0; i < rows.length && i < serversPresence.length; i++) {
                var row:Object = rows[i];
                var data:Object = serversPresence[i];
                row.mcOnLineFriends.gotoAndStop(int(data.friends)>0 ? "YES" : "NO");
                var fill:int = Math.ceil(Number(data.percentage)/20);
                for (var j:int = 1; j <= 5; j++) {
                    row["mcIndOn"+j].visible = j <= fill;
                    row["mcIndOff"+j].visible = j > fill;
                }
                row.mogobePopulation = int(data.online);
                row.mogobeFriends = int(data.friends);
                row.mogobeServerId = int(data.id);
            }
        }

        public function getServerInfo():Array {
            var result:Array = [];
            if (loginKind != "servers") return result;
            var rows:Array = [];
            collectServerRows(hookedServers,rows);
            for each (var row:Object in rows) {
                var fill:int = 0;
                for (var i:int = 1; i <= 5; i++) if (row["mcIndOn"+i].visible) fill++;
                var label:TextField = row.getChildByName("mogobeOnlineCount") as TextField;
                result.push({id:row.mogobeServerId,name:row.txtName.text,online:row.mogobePopulation,
                    friends:row.mogobeFriends,friendIcon:row.mcOnLineFriends.currentLabel,
                    fill:fill,text:label == null ? "" : label.text});
            }
            return result;
        }

        private function collectText(node:DisplayObject):String {
            if (!node.visible) return "";
            if (node is TextField) return TextField(node).text;
            var text:String = "";
            var container:DisplayObjectContainer = node as DisplayObjectContainer;
            if (container != null) for (var i:int = 0; i < container.numChildren; i++) text += collectText(container.getChildAt(i));
            return text;
        }

        private function currentPopup():Object {
            if (mainClip == null) return null;
            var managerClass:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.view.popups.PopupsManeger") as Class;
            var popup:Object = Object(managerClass).getInstance().CurrentPopup;
            if (popup != null && popup.baseView != null && popup.baseView.stage != null && socialPopupStack.indexOf(popup) == -1) socialPopupStack.push(popup);
            for (var i:int = socialPopupStack.length-1; i >= 0; i--) {
                if (socialPopupStack[i].baseView == null || socialPopupStack[i].baseView.stage == null) socialPopupStack.splice(i,1);
            }
            if (popup != null && popup.baseView != null && popup.baseView.stage != null) return popup;
            return socialPopupStack.length == 0 ? null : socialPopupStack[socialPopupStack.length-1];
        }

        private function currentProfile():Object {
            var popup:Object = currentPopup();
            return popup != null && (popup.PopupId == 7 || popup.PopupId == 8) ? popup : null;
        }

        public function setSocialState(state:Object):void {
            socialState = {};
            for each (var name:String in state.muted_names) socialState["$"+name] = true;
            var offer:MovieClip = findNamed(mainClip,"btnBodyOffer",0) as MovieClip;
            if (offer != null) {
                offer.visible = int(state.pending_requests) > 0;
                if ("txtBodyOffers" in offer) offer.txtBodyOffers.text = String(state.pending_requests);
            }
        }

        private function displayedMute(name:String):Boolean {
            var pending:Object = pendingMutes["$"+name];
            return pending == null ? socialState["$"+name] == true : Boolean(pending.muted);
        }

        private function inside(node:DisplayObject, parent:DisplayObject):Boolean {
            while (node != null) {
                if (node == parent) return true;
                node = node.parent;
            }
            return false;
        }

        private function socialClick(event:MouseEvent):void {
            clearFriendHover();
            var popup:Object = currentProfile();
            if (popup == null || popup.PopupId != 8) return;
            var button:DisplayObject = findNamed(popup.baseView,"btnBend",0);
            if (!inside(event.target as DisplayObject,button)) return;
            var nick:TextField = profileField(popup.baseView,"txtName");
            if (nick == null || nick.text == "") return;
            event.preventDefault();
            event.stopImmediatePropagation();
            var muted:Boolean = !displayedMute(nick.text);
            var sequence:int = ++muteSequence;
            pendingMutes["$"+nick.text] = {muted:muted, sequence:sequence};
            updateProfileCounters();
            ExternalInterface.call("onMogobeMuteChanged",nick.text,muted,sequence);
        }

        public function finishMuteChange(name:String, sequence:int, success:Boolean, muted:Boolean):void {
            if (success) socialState["$"+name] = muted;
            var pending:Object = pendingMutes["$"+name];
            if (pending == null || int(pending.sequence) != sequence) return;
            delete pendingMutes["$"+name];
            updateProfileCounters();
            var popup:Object = currentProfile();
            if (popup == null || popup.PopupId != 8) return;
            var nick:TextField = profileField(popup.baseView,"txtName");
            if (nick != null && nick.text == name) {
                // Ask through the original controller so its private Button
                // wrappers also refresh permission-dependent buttons.
                var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.AvatarEvent") as Class;
                popup.dispatchEvent(new cls(Object(cls).ASK_DATA_EVT,"user__getUserCardInfo",{userName:name,userId:popup.Data.userId},-1));
            }
        }

        public function chooseOriginalServer():Boolean {
            if (loginKind != "servers" || hookedServers == null || hookedServers.stage == null) return false;
            var rows:Array = [];
            collectServerRows(hookedServers,rows);
            if (rows.length == 0) return false;
            rows[0].dispatchEvent(new MouseEvent(MouseEvent.CLICK,true));
            return true;
        }

        private function friendControl(node:DisplayObject):Object {
            var popup:Object = currentPopup();
            if (popup == null || popup.PopupId != 24 || !inside(node,popup.baseView)) return null;
            while (node != null && node != popup.baseView) {
                var id:int = 0;
                var section:String = "BuddyList";
                var type:String = getQualifiedClassName(node);
                if (node.name == "btnClose") { id = 3; section = "Buttons"; }
                else if (node.name == "btnBuddyTab") id = 1;
                else if (node.name == "btnIgnorTab") id = 2;
                else if (node.name == "btnRequestTab") id = 3;
                else if (type == "mlUserOnLine" || type == "mlUserOffline") id = 4;
                else if (type == "btnAddBuddy") id = 5;
                else if (type == "btnRemoveBuddy") {
                    var line:DisplayObject = node.parent;
                    while (line != null && !("buddy" in Object(line))) line = line.parent;
                    var status:int = line == null ? 2 : Object(line).buddy.Status;
                    id = status == 1 ? 6 : status == 3 ? 10 : 8;
                }
                else if (type == "btnBestBuddy") {
                    var owner:DisplayObject = node.parent;
                    while (owner != null && !("buddy" in Object(owner))) owner = owner.parent;
                    id = owner != null && Object(owner).buddy.Status == 4 ? 11 : 7;
                }
                if (id != 0) {
                    var language:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.LanguageManager") as Class;
                    return {clip:node, text:Object(language).getInstance().getMessage(id,section)};
                }
                node = node.parent;
            }
            return null;
        }

        private function hoverFrame(clip:MovieClip, label:String):void {
            if (clip == null || clip.currentLabel == "GREYOUT") return;
            for each (var frame:Object in clip.currentLabels) if (frame.name == label) {
                clip.gotoAndStop(label);
                return;
            }
        }

        private function friendMouseOver(event:MouseEvent):void {
            var descriptor:Object = friendControl(event.target as DisplayObject);
            if (descriptor == null) return;
            event.stopImmediatePropagation();
            if (friendHover == descriptor.clip) return;
            clearFriendHover();
            friendHover = descriptor.clip as MovieClip;
            friendHoverText = String(descriptor.text);
            friendHoverTime = getTimer();
            hoverFrame(friendHover,"OVER");
            refreshFriendsFonts();
        }

        private function friendMouseOut(event:MouseEvent):void {
            var descriptor:Object = friendControl(event.target as DisplayObject);
            if (descriptor == null) return;
            event.stopImmediatePropagation();
            if (friendHover != null && inside(event.relatedObject as DisplayObject,friendHover)) return;
            clearFriendHover();
            refreshFriendsFonts();
        }

        private function clearFriendHover():void {
            hoverFrame(friendHover,"OUT");
            friendHover = null;
            friendHoverText = "";
            if (friendTooltip != null && friendTooltip.parent != null) friendTooltip.parent.removeChild(friendTooltip);
            friendTooltip = null;
        }

        private function updateFriendTooltip():void {
            var popup:Object = currentPopup();
            if (friendHover == null) return;
            if (friendHover.stage == null || popup == null || popup.PopupId != 24 ||
                !inside(friendHover,popup.baseView) || !friendHover.hitTestPoint(stage.mouseX,stage.mouseY,true)) {
                clearFriendHover();
                return;
            }
            if (friendTooltip != null || getTimer()-friendHoverTime < 800) return;
            // Match original AltPopUp's white box and Arial 10, while keeping
            // it out of hit testing and disposing it with the hovered control.
            var text:TextField = new TextField();
            text.defaultTextFormat = new TextFormat("Arial",10,0,false,false,false,null,null,TextFormatAlign.CENTER);
            text.embedFonts = true;
            text.text = friendHoverText;
            text.width = text.textWidth+6;
            text.height = text.textHeight+4;
            text.selectable = false;
            friendTooltip = new Sprite();
            friendTooltip.mouseEnabled = false;
            friendTooltip.mouseChildren = false;
            friendTooltip.graphics.lineStyle(0,0);
            friendTooltip.graphics.beginFill(0xFFFFFF);
            friendTooltip.graphics.drawRect(0,0,text.width,text.height);
            friendTooltip.graphics.endFill();
            friendTooltip.addChild(text);
            friendTooltip.x = Math.max(0,Math.min(768-text.width,mouseX-text.width/2));
            friendTooltip.y = mouseY-text.height-10 > 0 ? mouseY-text.height-10 : mouseY+16;
            addChild(friendTooltip);
        }

        public function getFriendsTooltipInfo():Object {
            return {visible:friendTooltip != null,text:friendTooltip == null ? "" : collectText(friendTooltip)};
        }

        private function childTypes(holder:DisplayObjectContainer):Array {
            var result:Array = [];
            for (var i:int = 0; i < holder.numChildren; i++) result.push(getQualifiedClassName(holder.getChildAt(i)));
            return result;
        }

        public function getWorldCursor():Object {
            var cursor:DisplayObject = stage.getChildByName("MouseCursor");
            if (cursor == null) return null;
            return {type:getQualifiedClassName(cursor),x:cursor.x,y:cursor.y};
        }

        public function getWorldEffects():Array {
            var result:Array = [];
            if (worldAvatar == null || worldAvatar.parent == null) return result;
            var holder:DisplayObjectContainer = worldAvatar.parent;
            for (var i:int = 0; i < holder.numChildren; i++) {
                var child:DisplayObject = holder.getChildAt(i);
                var type:String = getQualifiedClassName(child);
                if (type.indexOf("mlIco_") == 0) result.push({type:type, x:child.x, y:child.y});
            }
            return result;
        }

        public function getSocialPopupInfo():Object {
            var popup:Object = currentPopup();
            if (popup == null) return null;
            var rows:Array = [];
            var holder:DisplayObjectContainer = findNamed(popup.baseView,"mcListPlaceHolder",0) as DisplayObjectContainer;
            if (popup.PopupId == 24 && holder != null && holder.numChildren > 0) {
                var list:DisplayObjectContainer = holder.getChildAt(0) as DisplayObjectContainer;
                for (var i:int = 0; list != null && i < list.numChildren; i++) {
                    var row:Object = list.getChildAt(i);
                    if ("buddy" in row) rows.push({userName:row.buddy.BuddyName, status:row.buddy.Status,
                        serverName:row.buddy.ServerName, text:collectText(row as DisplayObject)});
                }
            }
            return {popupId:popup.PopupId, rows:rows};
        }

        public function getSocialRowControlBounds(name:String, action:String):Object {
            var popup:Object = currentPopup();
            if (popup == null || popup.PopupId != 24) return null;
            var row:DisplayObjectContainer = findNamed(popup.baseView,name,0) as DisplayObjectContainer;
            if (row == null) return null;
            var holderName:String = action == "name" ? "mcNameHolder" : action == "primary" ? "mcBtnHolder1" : "mcBtnHolder2";
            var holder:DisplayObjectContainer = row.getChildByName(holderName) as DisplayObjectContainer;
            if (holder == null || holder.numChildren == 0) return null;
            var bounds:Rectangle = holder.getChildAt(0).getBounds(this);
            return {x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height};
        }

        private function renderFriendField(view:Object, key:String, name:String, value:String):void {
            var original:TextField = view[key] as TextField;
            var holder:DisplayObjectContainer = DisplayObject(view).parent;
            if (holder == null) return;
            var rendered:TextField = holder.getChildByName(name) as TextField;
            if (rendered == null && original != null && original.parent != null) {
                var fonts:Class = ApplicationDomain.currentDomain.getDefinition("FontClass") as Class;
                rendered = Object(fonts).getInstance().addText(original,value);
                rendered.name = name;
                rendered.mouseEnabled = false;
                // Keep labels outside the OVER/OUT timeline, as for item icons.
                moveGridDecoration(rendered,holder);
            }
            if (rendered != null) rendered.visible = true;
            // OVER/OUT frames recreate the movie's sample text. Keep the
            // persistent embedded-font label and suppress each new sample.
            if (original != null && original != rendered && original.parent != null) original.visible = false;
            if (rendered != null && rendered.text != value) rendered.text = value;
        }

        private function refreshFriendsFonts():void {
            var popup:Object = currentPopup();
            if (popup == null || popup.PopupId != 24) return;
            var holder:DisplayObjectContainer = findNamed(popup.baseView,"mcListPlaceHolder",0) as DisplayObjectContainer;
            if (holder == null || holder.numChildren == 0) return;
            var list:DisplayObjectContainer = holder.getChildAt(0) as DisplayObjectContainer;
            for (var i:int = 0; list != null && i < list.numChildren; i++) {
                var row:Object = list.getChildAt(i);
                if (!("buddy" in row) || !("mcNameHolder" in row) || row.mcNameHolder.numChildren == 0) continue;
                var nameView:Object = row.mcNameHolder.getChildAt(0);
                renderFriendField(nameView,"txtName","mogobeBuddyName",String(row.buddy.BuddyName));
                renderFriendField(nameView,"txtServer","mogobeBuddyServer",row.buddy.ServerName == null ? "" : String(row.buddy.ServerName));
                // Offline OVER uses a different timeline text instance on its
                // first visit. Its public txtName reference may still point at
                // OUT, so suppress all authored samples, not just that reference.
                suppressFriendSamples(nameView as DisplayObject);
            }
        }

        private function suppressFriendSamples(node:DisplayObject):void {
            if (node is TextField || node is StaticText) {
                node.visible = false;
                return;
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            for (var i:int = 0; holder != null && i < holder.numChildren; i++) suppressFriendSamples(holder.getChildAt(i));
        }

        private function hideLuxuryCurrency(view:DisplayObjectContainer):void {
            var amount:TextField = profileField(view,"txtAmount_2");
            if (amount != null) amount.visible = false;
            // The original p_7 places the separate blue currency icon at
            // (303,338.5), sprite 146. Hide the complete sprite, including shadow.
            for (var i:int = 0; i < view.numChildren; i++) {
                var child:DisplayObject = view.getChildAt(i);
                if (Math.abs(child.x-303)<0.2 && Math.abs(child.y-338.5)<0.2 && child.width<40 && child.height<40) child.visible = false;
                // Original shape 144 contains all five counter pictograms.
                // Keep the original vector paths and isolate the four used
                // icons with masks, then center each over its own counter.
                var bounds:Rectangle = child.getBounds(view);
                if (child is Shape && child != Object(view).mogobeProfileIconSource &&
                    Math.abs(bounds.x-159.9)<0.2 && Math.abs(bounds.y-337.5)<0.2 && Math.abs(bounds.width-170)<0.2 &&
                    Object(view).mogobeProfileIconsPrepared != true && profileIconDomain != null) {
                    Object(view).mogobeProfileIconSource = child;
                    child.visible = false;
                    Object(view).mogobeProfileIconsPrepared = true;
                    var cuts:Array = [159.9,190,225,261,296];
                    var authored:Array = [168.9,203.4,239.4,275.4];
                    var targets:Array = [182.125,218.125,254.125,290.125];
                    for (var iconIndex:int = 0; iconIndex < 4; iconIndex++) {
                        var holder:Sprite = new Sprite();
                        holder.name = "mogobeProfileIcon"+iconIndex;
                        holder.mouseEnabled = false;
                        holder.mouseChildren = false;
                        var iconClass:Class = profileIconDomain.getDefinition("MogobeProfileCounterArtwork") as Class;
                        var icon:DisplayObject = new iconClass() as DisplayObject;
                        holder.addChild(icon);
                        var iconMask:Shape = new Shape();
                        iconMask.graphics.beginFill(0);
                        iconMask.graphics.drawRect(cuts[iconIndex],330,cuts[iconIndex+1]-cuts[iconIndex],32);
                        iconMask.graphics.endFill();
                        holder.addChild(iconMask);
                        icon.mask = iconMask;
                        holder.x = targets[iconIndex]-authored[iconIndex];
                        view.addChild(holder);
                    }
                }
            }
            var keys:Array = ["txtNewMsgs","txtFriends","txtAge","txtAmount_1"];
            var centers:Array = [182.125,218.125,254.125,290.125];
            for (var j:int = 0; j < keys.length; j++) {
                var field:TextField = profileField(view,keys[j]);
                // Wait for the original FontClass replacement; moving the
                // authored source would confuse its controller's own layout.
                if (field == null || field == Object(view)[keys[j]]) continue;
                var format:TextFormat = field.defaultTextFormat;
                format.align = TextFormatAlign.CENTER;
                format.leftMargin = 0;
                format.rightMargin = 0;
                format.indent = 0;
                field.defaultTextFormat = format;
                field.setTextFormat(format);
                var rect:Rectangle = field.getBounds(view);
                field.x += Number(centers[j])-rect.x-rect.width/2;
            }
        }

        private function profileField(view:DisplayObjectContainer, key:String):TextField {
            if (!(key in Object(view))) return null;
            var named:TextField = view.getChildByName("mogobeProfile_"+key) as TextField;
            if (named != null) return named;
            var source:TextField = Object(view)[key] as TextField;
            if (source == null) return null;
            if (source.parent != null) return source;
            // Original FontClass.addText replaces the source with an unnamed
            // embedded-font TextField. Match the original centered rectangle.
            for (var i:int = 0; i < view.numChildren; i++) {
                var field:TextField = view.getChildAt(i) as TextField;
                if (field != null && Math.abs(field.y - source.y) < 1 &&
                    Math.abs(field.x + field.width / 2 - source.x - source.width / 2) < 2) {
                    field.name = "mogobeProfile_"+key;
                    return field;
                }
            }
            return null;
        }

        private function updateProfileCounters():void {
            var popup:Object = currentProfile();
            if (popup == null) return;
            var targetId:int = int(popup.Data.userId);
            var targetName:String = popup.Data.userName == null ? "" : String(popup.Data.userName);
            var targetKey:String = targetId > 0 ? "id:"+targetId : targetName;
            if (targetKey != "" && Object(popup.baseView).mogobeProfileRequestedKey != targetKey) {
                Object(popup.baseView).mogobeProfileRequestedKey = targetKey;
                ExternalInterface.call("onMogobeProfileShown");
            }
            if (Number(Object(popup.baseView).mogobeScoreValue) >= 1024000) {
                var maxIndicator:MovieClip = popup.baseView.getChildByName("mogobeLevelIndicator") as MovieClip;
                if (maxIndicator != null) {
                    maxIndicator.gotoAndStop("ScoreLevel_11");
                    var maxFill:MovieClip = findNamed(maxIndicator,"mc",0) as MovieClip;
                    if (maxFill != null) maxFill.gotoAndStop(maxFill.totalFrames);
                }
            }
            var adminMark:DisplayObject = findNamed(popup.baseView,"mcMember",0);
            if (adminMark != null) {
                if (adminMark is flash.display.InteractiveObject) flash.display.InteractiveObject(adminMark).mouseEnabled = false;
                if (adminMark is DisplayObjectContainer) DisplayObjectContainer(adminMark).mouseChildren = false;
            }
            if (popup.PopupId == 7) {
                hideLuxuryCurrency(popup.baseView);
                var view:Object = popup.baseView;
                if (view.mogobeProfilePreparing == true) {
                    var coins:TextField = profileField(popup.baseView,"txtAmount_1");
                    if (coins != null && coins != view.txtAmount_1 && view.mogobeProfileIconsPrepared == true) {
                        view.mogobeProfilePreparing = false;
                        view.visible = true;
                    }
                }
            }
            if (popup.PopupId == 8) {
                var nick:TextField = profileField(popup.baseView,"txtName");
                var mute:MovieClip = findNamed(popup.baseView,"btnBend",0) as MovieClip;
                if (nick != null && mute != null) mute.gotoAndStop(displayedMute(nick.text) ? "CHEKED" : "UNCHECKED");
            }
            if (worldAvatar == null || worldAvatar.parent == null) return;
            var holder:DisplayObjectContainer = worldAvatar.parent;
            for (var i:int = 0; i < holder.numChildren; i++) {
                var avatar:DisplayObject = holder.getChildAt(i);
                if (int(avatar.name) != int(popup.Data.userId)) continue;
                var type:String = getQualifiedClassName(avatar);
                if (type != "worlds4u.view.avatar::MyAvatar" && type != "worlds4u.view.avatar::AvatarDocView") continue;
                var user:Object = Object(avatar).User;
                var age:TextField = profileField(popup.baseView, "txtAge");
                var friends:TextField = profileField(popup.baseView, "txtFriends");
                if (age != null && age.text != String(user.getVaribale("age"))) age.text = String(user.getVaribale("age"));
                if (friends != null && friends.text != String(user.getVaribale("friends"))) friends.text = String(user.getVaribale("friends"));
                return;
            }
        }

        private function experienceLevel(score:int):int {
            var thresholds:Array = [1000,2000,4000,8000,16000,32000,64000,124000,256000,512000,1024000];
            var level:int = 1;
            for each (var threshold:int in thresholds) if (score >= threshold) level++;
            return level;
        }

        public function setProfileProgress(data:Object):void {
            var popup:Object = currentProfile();
            if (popup == null || profileIconDomain == null) return;
            var targetId:int = int(popup.Data.userId);
            if (targetId > 0 && targetId != int(data.userId)) return;
            if (targetId <= 0 && String(popup.Data.userName).toLowerCase() != String(data.userName).toLowerCase()) return;
            var view:Object = popup.baseView;
            view.mogobeProfileUserId = int(data.userId);
            var admin:DisplayObject = findNamed(popup.baseView,"mcMember",0);
            if (admin != null) admin.visible = Boolean(data.isAdmin);
            var score:int = int(data.score);
            if (view.mogobeScoreValue === score) return;
            var original:MovieClip = findNamed(popup.baseView,"mcScore",0) as MovieClip;
            if (original == null) return;
            original.visible = false;
            original.mouseEnabled = false;
            original.mouseChildren = false;
            var indicator:MovieClip = popup.baseView.getChildByName("mogobeLevelIndicator") as MovieClip;
            if (indicator == null) {
                var cls:Class = profileIconDomain.getDefinition("MogobeScoreIndicator") as Class;
                indicator = new cls() as MovieClip;
                indicator.name = "mogobeLevelIndicator";
                indicator.transform.matrix = original.transform.matrix;
                popup.baseView.addChild(indicator);
                indicator.addEventListener(Event.REMOVED_FROM_STAGE,function(event:Event):void {
                    if (view.mogobeExperienceController != null) view.mogobeExperienceController.disableEvents();
                });
            }
            if (view.mogobeExperienceController != null) view.mogobeExperienceController.disableEvents();
            cls = ApplicationDomain.currentDomain.getDefinition("worlds4u.view.UserExperience") as Class;
            view.mogobeExperienceController = new cls(indicator,score);
            if (score >= 1024000) {
                indicator.gotoAndStop("ScoreLevel_11");
                var fill:MovieClip = findNamed(indicator,"mc",0) as MovieClip;
                if (fill != null) fill.gotoAndStop(fill.totalFrames);
            }
            view.mogobeScoreValue = score;
        }

        public function getExperienceInfo():Object {
            return {shown:scoreSignsShown,last:lastScoreSign};
        }

        public function getProfileInfo():Object {
            var popup:Object = currentProfile();
            if (popup == null) return null;
            var view:DisplayObjectContainer = popup.baseView;
            var nick:TextField = profileField(view, "txtName");
            var age:TextField = profileField(view, "txtAge");
            var friends:TextField = profileField(view, "txtFriends");
            var inventory:String = "";
            if ("mcAvatarInventory" in Object(view) && Object(view).mcAvatarInventory != null) inventory = Object(view).mcAvatarInventory.mcTabs.currentLabel;
            var counters:Array = [];
            for each (var key:String in ["txtNewMsgs","txtFriends","txtAge","txtAmount_1"]) {
                var counter:TextField = profileField(view,key);
                if (counter == null) continue;
                var rect:Rectangle = counter.getBounds(view);
                counters.push({name:key,center:rect.x+rect.width/2,align:counter.defaultTextFormat.align});
            }
            var iconBoxes:Array = [];
            for (var iconIndex:int = 0; iconIndex < 4; iconIndex++) {
                var holder:DisplayObjectContainer = view.getChildByName("mogobeProfileIcon"+iconIndex) as DisplayObjectContainer;
                if (holder != null && holder.numChildren == 2) {
                    var box:Rectangle = holder.getChildAt(1).getBounds(this);
                    iconBoxes.push({x:box.x,y:box.y,width:box.width,height:box.height});
                }
            }
            var luxuryIconVisible:Boolean = false;
            for (var i:int = 0; i < view.numChildren; i++) {
                var child:DisplayObject = view.getChildAt(i);
                if (Math.abs(child.x-303)<0.2 && Math.abs(child.y-338.5)<0.2 && child.width<40 && child.height<40 && child.visible) luxuryIconVisible = true;
            }
            var langClass:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.LanguageManager") as Class;
            var numericLevel:int = experienceLevel(int(Object(view).mogobeScoreValue));
            return {levelName:Object(langClass).getInstance().getMessage(numericLevel == 12 ? 0 : numericLevel,"UserExperience"),score:Object(view).mogobeScoreValue,level:numericLevel,iconBoxes:iconBoxes,visible:view.visible,counters:counters,luxuryIconVisible:view.visible && luxuryIconVisible,popupId:popup.PopupId, userId:Object(view).mogobeProfileUserId == null ? int(popup.Data.userId) : int(Object(view).mogobeProfileUserId), userName:popup.Data.userName != null ? String(popup.Data.userName) : nick == null ? "" : nick.text,
                days:age == null ? "" : age.text, friends:friends == null ? "" : friends.text, inventory:inventory,
                adminBadge:findNamed(view,"mcMember",0) != null && findNamed(view,"mcMember",0).visible,
                muted:nick != null && displayedMute(nick.text),
                mutePending:nick != null && pendingMutes["$"+nick.text] != null,
                muteFrame:findNamed(view,"btnBend",0) is MovieClip ? MovieClip(findNamed(view,"btnBend",0)).currentLabel : "",
                luxuryVisible:view.visible && profileField(view,"txtAmount_2") != null && profileField(view,"txtAmount_2").visible};
        }

        public function getProfileControlBounds(name:String):Object {
            var popup:Object = currentPopup();
            if (popup == null) return null;
            var control:DisplayObject = findNamed(popup.baseView, name, 0);
            if (control == null) return null;
            var bounds:Rectangle = control.getBounds(this);
            return {x:bounds.x, y:bounds.y, width:bounds.width, height:bounds.height};
        }

        private function collectOutfitClips(node:DisplayObject, result:Array):void {
            var type:String=getQualifiedClassName(node);
            if (type.indexOf("mlIconSItem")==0 || type.indexOf("mlIconWItem")==0 || type.indexOf("mlBigItem")==0) {
                var bounds:Rectangle=node.getBounds(this);
                result.push({type:type,frame:node is MovieClip?MovieClip(node).currentFrame:0,label:node is MovieClip?MovieClip(node).currentLabel:"",x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height});
                return;
            }
            var holder:DisplayObjectContainer=node as DisplayObjectContainer;
            for(var i:int=0;holder!=null && i<holder.numChildren;i++) collectOutfitClips(holder.getChildAt(i),result);
        }

        public function getInventoryInfo():Object {
            var popup:Object=currentProfile();
            if(popup==null)return null;
            var cells:Array=[]; collectInventoryCells(popup.baseView,cells);
            var clothing:Array=[];collectOutfitClips(popup.baseView,clothing);
            var tabs:MovieClip = findNamed(popup.baseView,"mcTabs",0) as MovieClip;
            return {tab:tabs == null ? "" : tabs.currentLabel,cells:cells,clothing:clothing};
        }

        private function collectInventoryCells(node:DisplayObject,cells:Array):void {
            if(getQualifiedClassName(node)=="worlds4u.common.uiControls.DataGrid::GridCell") {
                var data:Object=Object(node).Data;
                var bounds:Rectangle=node.getBounds(this);
                cells.push({id:data.ID,typeId:data.TypeId,mainType:data.MType,visible:node.visible,x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height});return;
            }
            var holder:DisplayObjectContainer=node as DisplayObjectContainer;
            for(var i:int=0;holder!=null && i<holder.numChildren;i++)collectInventoryCells(holder.getChildAt(i),cells);
        }

        private function avatarCameraClick(event:MouseEvent):void {
            var popup:Object = currentProfile();
            if (popup == null || popup.PopupId != 7) return;
            var camera:DisplayObject = findNamed(popup.baseView,"btnCamera",0);
            var target:DisplayObject = event.target as DisplayObject;
            while (target != null && target != camera) target = target.parent;
            if (target == null) return;
            event.stopImmediatePropagation();
            event.preventDefault();
            try {
                var holder:DisplayObjectContainer = findNamed(popup.baseView,"mcAvatarHolder",0) as DisplayObjectContainer;
                var avatar:DisplayObject = findAvatarPortrait(holder);
                if (avatar == null) return;
                var bounds:Rectangle = avatar.getBounds(avatar);
                var scale:Number = 2;
                var image:BitmapData = new BitmapData(Math.ceil(bounds.width*scale)+24,Math.ceil(bounds.height*scale)+24,false,0xFFFFFF);
                image.draw(avatar,new Matrix(scale,0,0,scale,12-bounds.x*scale,12-bounds.y*scale));
                var encoder:Class = ApplicationDomain.currentDomain.getDefinition("com.adobe.images.JPGEncoder") as Class;
                var bytes:ByteArray = new encoder(90).encode(image);
                image.dispose();
                ExternalInterface.call("onMogobeAvatarPhoto",encodePhoto(bytes));
            } catch(error:Error) { ExternalInterface.call("showMogobePopup","Не удалось получить изображение могоби: "+error.message); }
        }

        private function findAvatarPortrait(node:DisplayObject):DisplayObject {
            if (node == null) return null;
            if (getQualifiedClassName(node) == "mlCardAvatar") return node;
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            for (var i:int=0;holder != null && i<holder.numChildren;i++) {
                var result:DisplayObject = findAvatarPortrait(holder.getChildAt(i));
                if (result != null) return result;
            }
            return null;
        }

        private function encodePhoto(bytes:ByteArray):String {
            var alphabet:String="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
            var result:String="";
            bytes.position=0;
            while(bytes.bytesAvailable>0) {
                var a:int=bytes.readUnsignedByte();
                var b:int=bytes.bytesAvailable>0?bytes.readUnsignedByte():-1;
                var c:int=bytes.bytesAvailable>0?bytes.readUnsignedByte():-1;
                result+=alphabet.charAt(a>>2)+alphabet.charAt(((a&3)<<4)|(b<0?0:b>>4));
                result+=b<0?"=":alphabet.charAt(((b&15)<<2)|(c<0?0:c>>6));
                result+=c<0?"=":alphabet.charAt(c&63);
            }
            return result;
        }

        private function originalDisplayAdded(event:Event):void {
            var view:DisplayObject = event.target as DisplayObject;
            observeSpeechBalloon(view);
            prepareRoomView(view);
            if (view != null && getQualifiedClassName(view) == "mlWorldScoreSign") {
                scoreSignsShown++;
                lastScoreSign = collectText(view);
            }
            if (view is DisplayObjectContainer && getQualifiedClassName(view) == "mlPopup_33") {
                shopWindowsCreated++;
                prepareShopLayout(view as DisplayObjectContainer);
                // The original direct hit path can also run when already standing
                // at a shop. Keep its legacy window hidden until catalog adaptation.
                if (shopData == null && originalShopPointAtAvatar() != null) view.visible=false;
            }
            if (view != null && getQualifiedClassName(view) == "mlPopup_3") {
                // Hold the original popup before its first paint until the
                // cached island/button have been attached in this same frame.
                view.visible = false;
            }
            if (view != null && getQualifiedClassName(view) == "mlPopup_7") {
                // The asynchronous asset loader can draw this card before the
                // next timeline tick. Do not expose its unadapted first frame.
                view.visible = false;
                Object(view).mogobeProfilePreparing = true;
            }
        }

        private function prepareRoomView(view:DisplayObject):void {
            if (view == null || getQualifiedClassName(view) != "mlMagicForest" || Object(view).mogobeExitsPrepared) return;
            var entry:MovieClip = findNamed(view,"mcEntryPoint_440",0) as MovieClip;
            if (entry == null) return;
            // The original MagicForest[4] leaves this tree-door hit zone above
            // the stage. Preserve the original shape and restore its position.
            // Server geometry uses the same ENTRY_POSITIONS in the generator.
            // Include the front landing: the tree roots clip walks aimed at
            // the door itself, so the trigger must reach the accessible step.
            entry.x = 100;
            entry.y = 330;
            Object(view).mogobeExitsPrepared = true;
        }

        private function finishOriginalFrame(event:Event):void {
            updateFocusedInput();
            updateSpeechBalloons();
            if (stage != null) stage.invalidate();
            if (mainClip == null) return;
            refreshFriendsFonts();
            updateProfileCounters();
            updateWorldPanel();
            updateRoomAudio();
            watchOriginalShop();
            updateShopLayout();
            var profile:Object = currentProfile();
            if (profile != null) {
                updateInventory(profile);
                preserveGridDecorations(profile.baseView);
            }
            updateWorldMap();
        }

        private function finishOriginalRender(event:Event):void {
            updateFocusedInput();
            updateSpeechBalloons();
            // RENDER follows every descendant's frame scripts, including the
            // OVER frame which can recreate authored text after EXIT_FRAME.
            refreshFriendsFonts();
            var profile:Object = currentProfile();
            if (profile != null) {
                updateInventory(profile);
                preserveGridDecorations(profile.baseView);
            }
        }

        private var inventoryPopup:Object;
        private var inventoryFilter:Object;

        private function inventoryRequest(event:Event):void {
            if (Object(event).Cmd != "user__getInventoryItems" || inventoryPopup == null) return;
            var request:Object = Object(event).Data;
            var categories:Array = [];
            if (request.placeCategorys != null) for each (var category:Object in request.placeCategorys) categories.push(int(category));
            inventoryFilter = {mainType:int(request.mainType),categories:categories};
            var grid:Object = shopGrid(inventoryPopup.baseView,"ButtonDataGrid");
            if (grid == null) return;
            // Discard the previous tab synchronously; the original controller
            // otherwise leaves it visible until the network response arrives.
            grid.Data = [];
            grid.baind();
            prepareInventoryCells(grid as DisplayObject);
        }

        private function updateInventory(profile:Object):void {
            if (profile.PopupId != 7) return;
            if (inventoryPopup != profile) {
                if (inventoryPopup != null) inventoryPopup.removeEventListener("ASK_DATA_EVT",inventoryRequest);
                inventoryPopup = profile;
                inventoryFilter = null;
                profile.addEventListener("ASK_DATA_EVT",inventoryRequest,false,200);
            }
            var inventory:DisplayObject = findNamed(profile.baseView,"mcAvatarInventory",0);
            if (inventory != null) prepareInventoryCells(inventory);
        }

        private function prepareInventoryCells(node:DisplayObject):void {
            var type:String = getQualifiedClassName(node);
            if (type == "worlds4u.common.uiControls.DataGrid::GridCell") {
                // A GridCell first contains the authored example. Its real art
                // is attached asynchronously by ItemFactory, even from cache.
                var item:Object = Object(node).Data;
                var matches:Boolean = inventoryFilter == null || int(item.MType) == inventoryFilter.mainType;
                if (matches && inventoryFilter != null && inventoryFilter.categories.length > 0)
                    matches = inventoryFilter.categories.indexOf(int(item.PCat)) >= 0;
                // A response from a quickly abandoned tab can arrive after the
                // new request. Never paint rows outside the selected filter.
                node.visible = matches && findShopGraphic(node,"btnItem") != null;
                return;
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            for (var i:int = 0; holder != null && i < holder.numChildren; i++) prepareInventoryCells(holder.getChildAt(i));
        }

        private function preloadProfileIcons():void {
            if (profileIconLoader != null) return;
            profileIconLoader = new Loader();
            profileIconLoader.contentLoaderInfo.addEventListener(Event.COMPLETE,function(event:Event):void {
                profileIconDomain = profileIconLoader.contentLoaderInfo.applicationDomain;
                updateProfileCounters();
            });
            profileIconLoader.load(new URLRequest("/compat/ProfileCounterIcons.swf"),new LoaderContext(false,new ApplicationDomain()));
        }

        private function preloadWorldMap():void {
            if (mapAssetsLoader != null) return;
            mapAssetsLoader = new Loader();
            mapAssetsLoader.contentLoaderInfo.addEventListener(Event.COMPLETE,function(event:Event):void {
                mapAssetsDomain = mapAssetsLoader.contentLoaderInfo.applicationDomain;
                updateWorldMap();
            });
            mapAssetsLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,function(event:IOErrorEvent):void { mapAssetsError = event.text; });
            mapAssetsLoader.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR,function(event:SecurityErrorEvent):void { mapAssetsError = event.text; });
            mapAssetsLoads++;
            mapAssetsLoader.load(new URLRequest("/compat/WorldMapBumagLand.swf"),new LoaderContext(false,new ApplicationDomain()));
        }

        private function updateWorldMap():void {
            var popup:Object = currentPopup();
            if (popup == null || popup.PopupId != 3 || mapAssetsDomain == null) return;
            var view:MovieClip = popup.baseView as MovieClip;
            var map:DisplayObjectContainer = findNamed(view,"mcMap",0) as DisplayObjectContainer;
            if (map == null || Object(view).mogobeMapPrepared) return;
            Object(view).mogobeMapPrepared = true;
            var spaceship:MovieClip = map.getChildByName("mcBumagVale") as MovieClip;
            if (spaceship != null) {
                spaceship.visible = false;
                spaceship.mouseEnabled = false;
                spaceship.mouseChildren = false;
                Object(view).mogobeMapSpaceship = spaceship;
                map.removeChild(spaceship);
            }
            // The old standalone birch (sprite 54 at map depth 499) is next to
            // the imported portal. Match its authored transform, not its name:
            // this timeline object is unnamed and timeline names are read-only.
            for (var i:int = 0; i < map.numChildren; i++) {
                var tree:DisplayObject = map.getChildAt(i);
                var matrix:Matrix = tree.transform.matrix;
                if (Math.abs(matrix.tx-188.1)<0.01 && Math.abs(matrix.ty-52.05)<0.01 &&
                    Math.abs(matrix.a+0.17138671875)<0.00001 && Math.abs(matrix.d-0.1880950927734375)<0.00001) {
                    tree.visible = false;
                    Object(view).mogobeMapBirch = tree;
                    break;
                }
            }
            var fragmentClass:Class = mapAssetsDomain.getDefinition("MogobeBumagMapFragment") as Class;
            var scenery:MovieClip = new fragmentClass() as MovieClip;
            scenery.stop();
            scenery.name = "mogobeBumagIsland";
            scenery.mouseEnabled = false;
            scenery.mouseChildren = false;
            var buttonClip:MovieClip = scenery.getChildByName("mcBumagVale") as MovieClip;
            // Both layers retain the exact transforms from Russian map object
            // 286. No URL load or asynchronous display change happens on open.
            scenery.removeChild(buttonClip);
            map.addChildAt(scenery,0);
            map.addChild(buttonClip);
            var buttonClass:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.common.uiControls.Button") as Class;
            var button:Object = new buttonClass(buttonClip,"Бумагленд",false);
            button.name = "mcBumagVale";
            button.addEventListener(MouseEvent.CLICK,function(click:MouseEvent):void {
                click.stopImmediatePropagation();
                var avatarEvent:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.AvatarEvent") as Class;
                var config:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.common.AppConfig") as Class;
                popup.dispatchEvent(new avatarEvent(Object(avatarEvent).AVTARCHANGEROOM_EVT,"rooms__jumpToRoom",
                    {nameId:"BumagVale",userId:Object(config).MySfsUserId,userName:Object(config).MyUserName},-1));
                popup.dispatchEvent(new Event(Event.CLOSE));
                popup.disableEvents();
            });
            buttonClip.addEventListener(Event.REMOVED_FROM_STAGE,function(event:Event):void { button.destroy(); });
            Object(view).mogobeMapReady = true;
            view.visible = true;
        }

        public function getWorldMapInfo():Object {
            var popup:Object = currentPopup();
            if (popup == null || popup.PopupId != 3 || findNamed(popup.baseView,"mcMap",0) == null) return null;
            var button:MovieClip = findNamed(popup.baseView,"mcBumagVale",0) as MovieClip;
            var spaceship:DisplayObject = Object(popup.baseView).mogobeMapSpaceship as DisplayObject;
            var tree:DisplayObject = Object(popup.baseView).mogobeMapBirch as DisplayObject;
            var island:DisplayObject = findNamed(popup.baseView,"mogobeBumagIsland",0);
            return {ready:Object(popup.baseView).mogobeMapReady == true,visible:popup.baseView.visible,
                error:mapAssetsError,assetsReady:mapAssetsDomain != null,assetsLoads:mapAssetsLoads,
                birchFound:tree != null,birchVisible:tree != null && tree.visible,
                buttonClass:button == null ? "" : getQualifiedClassName(button),
                spaceshipVisible:spaceship != null && spaceship.visible,
                islandVisible:island != null && island.visible,
                buttonFrame:button == null ? "" : button.currentLabel,
                buttonFrames:button == null ? 0 : button.totalFrames};
        }

        private function prepareShopLayout(view:DisplayObjectContainer):void {
            if (view == null || Object(view).mogobeShopPrepared == true) return;
            var panel:DisplayObjectContainer = findNamed(view,"mcShop",0) as DisplayObjectContainer;
            if (panel == null) return;
            Object(view).mogobeShopPrepared = true;
            var luxury:DisplayObject = panel.getChildByName("txtAmount_2");
            if (luxury != null) luxury.visible = false;
            var amount:DisplayObject = panel.getChildByName("txtAmount_1");
            var coins:DisplayObject = panel.getChildByName("mcCoinsIcon");
            if (amount != null) amount.y += 20;
            if (coins != null) coins.y += 20;
            for (var i:int = 0; i < panel.numChildren; i++) {
                var child:DisplayObject = panel.getChildAt(i);
                var bounds:Rectangle = child.getBounds(panel);
                // Luxury icon and its authored shadow are separate objects.
                if ((Math.abs(child.x-173.05)<0.2 && Math.abs(child.y-295.85)<0.2) ||
                    (child is Shape && Math.abs(bounds.x-178.4)<0.2 && Math.abs(bounds.y-294.8)<0.2)) child.visible = false;
                if (child is Shape && Math.abs(bounds.x-180.1)<0.2 && Math.abs(bounds.y-267.3)<0.2) child.y += 20;
            }
        }

        private function updateShopLayout():void {
            var popup:Object = currentPopup();
            if (popup == null || getQualifiedClassName(popup.baseView) != "mlPopup_33") return;
            prepareShopLayout(popup.baseView);
            preserveGridDecorations(popup.baseView);
            var categories:Array = [];
            collectShopCategories(popup.baseView,categories);
            for each (var tab:DisplayObject in categories) {
                var strip:DisplayObjectContainer = tab.parent;
                strip.y = 0;
                var grid:DisplayObjectContainer = strip.parent;
                for (var n:int = 0; n < grid.numChildren; n++) {
                    var control:DisplayObject = grid.getChildAt(n);
                    if (getQualifiedClassName(control) == "fl.controls::ScrollBar") {
                        control.visible = false;
                        Object(control).enabled = false;
                        DisplayObjectContainer(control).mouseChildren = false;
                        flash.display.InteractiveObject(control).mouseEnabled = false;
                    }
                }
            }
            if (categories.length > 6) {
                // Retain the original buttons and hit handlers; fit extra tabs
                // into the authored six-column strip instead of a clipped row.
                var scale:Number = 6 / categories.length;
                for (var i:int = 0; i < categories.length; i++) {
                    var cell:DisplayObject = categories[i] as DisplayObject;
                    cell.scaleX = cell.scaleY = scale;
                    cell.x = i * 50 * scale;
                    cell.y = (50 - 50 * scale) / 2;
                    var siblings:DisplayObjectContainer = cell.parent;
                    for (var j:int = 0; j < siblings.numChildren; j++) {
                        var empty:DisplayObject = siblings.getChildAt(j);
                        if (getQualifiedClassName(empty) == "mlCategoryState") empty.visible = false;
                    }
                }
            }
            if (shopData == null || shopData.kind != "objects") return;
            var holder:DisplayObjectContainer = findNamed(popup.baseView,"mcBigDisplay",0) as DisplayObjectContainer;
            var selected:DisplayObject = holder == null ? null : holder.getChildByName("selectedItem");
            if (selected == null || Object(selected).mogobePreviewPrepared == true) return;
            var bounds:Rectangle = selected.getBounds(selected);
            if (bounds.width <= 0 || bounds.height <= 0) return;
            // Original mcBigDisplay white area: x=6.05..193.6, y=12.2..227.
            scale = Math.min(1,120 / bounds.width,140 / bounds.height);
            selected.scaleX = selected.scaleY = scale;
            selected.x = 99.825 - (bounds.x + bounds.width/2) * scale;
            selected.y = 119.6 - (bounds.y + bounds.height/2) * scale;
            Object(selected).mogobePreviewPrepared = true;
        }

        private function shopCategoryWheel(event:MouseEvent):void {
            if (shopPopup == null) return;
            var node:DisplayObject = event.target as DisplayObject;
            while (node != null && node != shopPopup.baseView) {
                if (getQualifiedClassName(node) == "worlds4u.common.uiControls.DataGrid::ScrollDataGrid") {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    return;
                }
                node = node.parent;
            }
        }

        private function moveGridDecoration(art:DisplayObject, cell:DisplayObjectContainer):void {
            var placement:Matrix = art.transform.matrix.clone();
            var holder:DisplayObjectContainer = art.parent;
            while (holder != null && holder != cell) {
                placement.concat(holder.transform.matrix);
                holder = holder.parent;
            }
            cell.addChild(art);
            art.transform.matrix = placement;
            if (art is flash.display.InteractiveObject) flash.display.InteractiveObject(art).mouseEnabled = false;
            if (art is DisplayObjectContainer) DisplayObjectContainer(art).mouseChildren = false;
        }

        private function preserveGridDecorations(node:DisplayObject):void {
            var type:String = getQualifiedClassName(node);
            var cell:DisplayObjectContainer = node as DisplayObjectContainer;
            if (cell == null) return;
            if (type == "worlds4u.common.uiControls.DataGrid::GridCellStore" ||
                type == "worlds4u.common.uiControls.DataGrid::CatCell" ||
                type == "worlds4u.common.uiControls.DataGrid::GridCell") {
                // StateButton changes the authored MovieClip frame on hover
                // and selection. Keep the original art/font outside that
                // timeline so a replacement mcItemHolder cannot discard them.
                var prefix:String = type == "worlds4u.common.uiControls.DataGrid::CatCell" ? "btnCat" : "btnItem";
                var art:DisplayObject = findShopGraphic(cell,prefix);
                if (art != null && art.parent != cell) moveGridDecoration(art,cell);
                if (type == "worlds4u.common.uiControls.DataGrid::GridCellStore") {
                    var price:TextField = cell.getChildByName("mogobeGridPrice") as TextField;
                    for (var i:int = 0; i < cell.numChildren; i++) {
                        var state:MovieClip = cell.getChildAt(i) as MovieClip;
                        if (state == null || !("txtPrice" in Object(state))) continue;
                        var source:TextField = profileField(state,"txtPrice");
                        if (price == null && art != null && source != null) {
                            source.name = "mogobeGridPrice";
                            moveGridDecoration(source,cell);
                            price = source;
                        } else if (source != null && source != price) source.visible = false;
                    }
                    if (price != null) {
                        price.visible = true;
                        price.text = String(Object(cell).Data.Price);
                    }
                }
                return;
            }
            for (i = 0; i < cell.numChildren; i++) preserveGridDecorations(cell.getChildAt(i));
        }

        private function countVisibleCategoryScrollers(node:DisplayObject):int {
            var count:int = getQualifiedClassName(node) == "fl.controls::ScrollBar" && node.visible ? 1 : 0;
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) count += countVisibleCategoryScrollers(holder.getChildAt(i));
            return count;
        }

        private function collectShopCategories(node:DisplayObject, result:Array):void {
            if (getQualifiedClassName(node) == "worlds4u.common.uiControls.DataGrid::CatCell") {
                result.push(node);
                return;
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) collectShopCategories(holder.getChildAt(i),result);
        }

        private function updateWorldPanel():void {
            var controls:DisplayObject = findNamed(mainClip,"mcControlButtons",0);
            if (controls == null) return;
            var dance:MovieClip = findNamed(controls,"mcDanceMove",0) as MovieClip;
            if (dance != null) {
                dance.visible = false;
                dance.mouseEnabled = false;
                dance.mouseChildren = false;
            }
            var field:TextField = findNamed(findNamed(controls,"mcChat",0),"txtSpeak",0) as TextField;
            if (field == null) return;
            if (Object(controls).mogobeChatPrepared != field) {
                Object(controls).mogobeChatPrepared = field;
                field.autoSize = TextFieldAutoSize.NONE;
                field.multiline = false;
                field.wordWrap = false;
                field.maxChars = 240;
                // Raise only the editable text. Leave the original input
                // background and send button at their authored positions.
                field.y -= 3;
            }
            updateChatHistory(controls as DisplayObjectContainer,field);
            // Formatting every frame resets the input's horizontal scrolling.
            // Only repair a direction change made by the original text manager.
            if (field.defaultTextFormat.align != TextFormatAlign.LEFT ||
                (field.length > 0 && field.getTextFormat().align != TextFormatAlign.LEFT)) {
                var format:TextFormat = field.defaultTextFormat;
                format.align = TextFormatAlign.LEFT;
                format.leftMargin = 0;
                format.rightMargin = 0;
                format.indent = 0;
                field.defaultTextFormat = format;
                field.setTextFormat(format);
            }
        }

        // BEGIN SHARED INPUT COMPATIBILITY
        // Ruffle 0.7.1 does not reveal native TextField selections when typing
        // or moving the caret. Keep this shared by the game and plain-SWF probe.
        private var inputCompatibilityState:Dictionary = new Dictionary(true);

        private function inputCaretX(field:TextField, index:int):Number {
            if (index <= 0) return 2;
            var previous:int = field.scrollH;
            field.scrollH = 0;
            var glyph:Rectangle = field.getCharBoundaries(index-1);
            field.scrollH = previous;
            return glyph == null ? field.textWidth+2 : glyph.right;
        }

        private function updateFocusedInput():void {
            if (stage == null) return;
            var field:TextField = stage.focus as TextField;
            if (field == null || field.type != "input" || field.stage == null) return;
            var state:Object = inputCompatibilityState[field];
            if (state == null) {
                // Cache only selection/layout metadata, never input contents.
                state={length:-1,caret:-1,line:-1,lines:-1,width:-1,height:-1};
                inputCompatibilityState[field]=state;
            }
            var length:int=field.length;
            var caret:int=field.caretIndex;
            var width:Number=field.getBounds(field).width;
            var line:int=length==0 ? 1 : field.getLineIndexOfChar(Math.min(caret,length-1))+1;
            if (caret == length) line=field.numLines;
            var changed:Boolean=state.length!=length || state.caret!=caret || state.line!=line ||
                state.lines!=field.numLines || state.width!=width || state.height!=field.height;
            if (length == 0 || field.wordWrap) {
                if (field.scrollH != 0) field.scrollH=0;
            } else {
                var endX:Number=field.multiline ? Math.max(field.textWidth+2,inputCaretX(field,length)) : inputCaretX(field,length);
                var maximum:int=Math.max(0,Math.ceil(endX-width+4));
                var target:int=field.scrollH;
                var x:Number=inputCaretX(field,caret);
                if (caret==length && !field.multiline) target=maximum;
                else if (caret==0) target=0;
                else if (x>target+width-4) target=Math.ceil(x-width+4);
                else if (x<target+2) target=Math.max(0,Math.floor(x-2));
                target=Math.max(0,Math.min(target,maximum));
                if (field.scrollH!=target) field.scrollH=target;
            }
            // Reveal edits/caret moves vertically. Do not snap manual wheel
            // scrolling back to the caret while the selection is unchanged.
            if (changed && field.numLines>1) {
                if (line<field.scrollV) field.scrollV=line;
                else if (line>field.bottomScrollV) {
                    var visible:int=Math.max(1,field.bottomScrollV-field.scrollV+1);
                    field.scrollV=Math.min(field.maxScrollV,Math.max(1,line-visible+1));
                    while (line>field.bottomScrollV && field.scrollV<field.maxScrollV) field.scrollV++;
                }
            }
            state.length=length;state.caret=caret;state.line=line;
            state.lines=field.numLines;state.width=width;state.height=field.height;
        }
        // END SHARED INPUT COMPATIBILITY

        private var chatHistoryLoader:Loader;
        private var chatHistoryDomain:ApplicationDomain;
        private var chatHistoryPanel:MovieClip;
        private var chatHistoryBody:DisplayObject;
        private var chatHistoryButton:MovieClip;
        private var chatHistoryHit:Sprite;
        private var chatHistoryBar:DisplayObject;
        private var chatHistoryMeasure:TextField;
        private var chatHistoryFormat:TextFormat;
        private var chatHistoryFields:Array = [];
        private var chatHistoryLayout:Array = [];
        private var chatHistoryRows:Array = [];
        private var chatHistoryNames:Array = [];
        private var chatHistoryTimes:Array = [];
        private var chatHistoryContent:String = "";
        private var chatHistoryAnchor:int = 0;
        private var chatHistoryLatest:int = 0;
        private var chatHistoryFollow:Boolean = true;
        private var chatHistoryOpen:Boolean = false;
        private var chatHistoryError:String = "";
        private var chatHistoryFillAlpha:int = 0;
        // Inner edges of original shape 294, translated by mcMessageHolder.
        // Keep its 40% black fill and two-pixel green border unchanged.
        private const historyTop:Number = -152.45;
        private const historyBottom:Number = 0.3;
        private const historyPadding:Number = 6;
        private const historySlots:int = 8;
        // Reserve the original font metrics and two-pixel top/bottom gutters.
        // Fields may overlap in those empty gutters; their glyphs never do.
        private const historyFieldHeight:Number = 21;
        private const historyLineHeight:Number = (152.75-12-21)/7;

        private function preloadChatHistory():void {
            chatHistoryLoader = new Loader();
            chatHistoryLoader.contentLoaderInfo.addEventListener(Event.COMPLETE,function(event:Event):void {
                chatHistoryDomain = chatHistoryLoader.contentLoaderInfo.applicationDomain;
            });
            chatHistoryLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,function(event:IOErrorEvent):void { chatHistoryError = event.text; });
            chatHistoryLoader.load(new URLRequest("/compat/ChatHistory.swf"),new LoaderContext(false,new ApplicationDomain()));
        }

        private function updateChatHistory(controls:DisplayObjectContainer, input:TextField):void {
            if (chatHistoryDomain == null) return;
            if (chatHistoryPanel == null) {
                var cls:Class = chatHistoryDomain.getDefinition("MogobeOriginalChatHistory") as Class;
                chatHistoryPanel = new cls() as MovieClip;
                chatHistoryPanel.name = "mogobeChatHistory";
                chatHistoryPanel.stop();
                chatHistoryBody = findNamed(chatHistoryPanel,"mcMessageHolder",0);
                var sample:BitmapData = new BitmapData(1,1,true,0);
                sample.draw(chatHistoryBody,new Matrix(1,0,0,1,-100,-50));
                chatHistoryFillAlpha = sample.getPixel32(0,0) >>> 24;
                sample.dispose();
                chatHistoryButton = findNamed(chatHistoryPanel,"btnPublicMessages",0) as MovieClip;
                chatHistoryButton.x += 2.15; // Align the original arrow with the pane's centre.
                chatHistoryButton.gotoAndStop(1);
                chatHistoryHit = new Sprite();
                chatHistoryHit.graphics.beginFill(0,0);
                chatHistoryHit.graphics.drawRect(45,-7.75,56,14.1);
                chatHistoryHit.graphics.endFill();
                chatHistoryHit.visible = false;
                chatHistoryButton.addChild(chatHistoryHit);
                chatHistoryButton.hitArea = chatHistoryHit;
                chatHistoryButton.buttonMode = true;
                chatHistoryButton.mouseChildren = false;
                chatHistoryButton.addEventListener(MouseEvent.CLICK,toggleChatHistory);
                chatHistoryButton.addEventListener(MouseEvent.ROLL_OVER,historyButtonOver);
                chatHistoryButton.addEventListener(MouseEvent.ROLL_OUT,historyButtonOut);
                var fontClass:Class = ApplicationDomain.currentDomain.getDefinition("FontClass") as Class;
                Object(fontClass).getInstance(); // Register the preserved Arial font.
                chatHistoryFormat = input.defaultTextFormat;
                chatHistoryFormat.font = Object(fontClass).FONT_ARIAL;
                chatHistoryFormat.bold = false;
                chatHistoryFormat.size = 12;
                chatHistoryFormat.color = 0xffffff;
                chatHistoryFormat.align = TextFormatAlign.LEFT;
                chatHistoryFormat.leading = 0;
                chatHistoryFormat.leftMargin = 0;
                chatHistoryFormat.rightMargin = 0;
                chatHistoryFormat.indent = 0;
                chatHistoryMeasure = new TextField();
                chatHistoryMeasure.embedFonts = true;
                chatHistoryMeasure.defaultTextFormat = chatHistoryFormat;
                chatHistoryMeasure.autoSize = TextFieldAutoSize.LEFT;
                for (var i:int=0;i<historySlots;i++) {
                    var field:TextField = new TextField();
                    field.name = "txtChatHistoryLine"+i;
                    field.embedFonts = true;
                    field.antiAliasType = "advanced";
                    field.defaultTextFormat = chatHistoryFormat;
                    field.multiline = false;
                    field.wordWrap = false;
                    field.selectable = true;
                    chatHistoryPanel.addChild(field);
                    chatHistoryFields.push(field);
                }
                chatHistoryPanel.addEventListener(MouseEvent.MOUSE_WHEEL,scrollChatHistory);
                chatHistoryPanel.addEventListener(MouseEvent.MOUSE_DOWN,historyMouseDown);
                chatHistoryPanel.addEventListener(MouseEvent.CLICK,function(event:MouseEvent):void {event.stopPropagation();});
                renderChatHistory(true);
            }
            if (chatHistoryPanel.parent != controls) controls.addChild(chatHistoryPanel);
            // Shape 110 is the original RU bar artwork. Match the HE source's
            // 0.15px offset from its top edge instead of floating above the input.
            chatHistoryBar = controls.getChildAt(0);
            var bar:Rectangle = chatHistoryBar.getBounds(controls);
            var anchor:Point = controls.globalToLocal(localToGlobal(new Point(384,0)));
            chatHistoryPanel.x = anchor.x-75.375;
            chatHistoryPanel.y = bar.top+0.15;
            // Preserve the source button's attachment to the pane's lower edge.
            chatHistoryButton.y = -4.9;
            chatHistoryBody.visible = chatHistoryOpen;
            for each (var line:TextField in chatHistoryFields) line.visible = chatHistoryOpen && line.length > 0;
        }

        private function historyMouseDown(event:MouseEvent):void {
            event.stopPropagation();
        }

        private function setHistoryButton(over:Boolean = false):void {
            // UNCHECKED (17) removes the upper artwork and draws the lower
            // button. CHEKED (13) retains the upper button; it is not "open".
            chatHistoryButton.gotoAndStop(chatHistoryOpen ? 17 : (over ? 5 : 1));
            chatHistoryButton.y = -4.9;
            chatHistoryHit.graphics.clear();
            chatHistoryHit.graphics.beginFill(0,0);
            chatHistoryHit.graphics.drawRect(45,chatHistoryOpen ? 5.25 : -7.75,56,14.1);
            chatHistoryHit.graphics.endFill();
        }

        private function historyButtonOver(event:MouseEvent):void {
            setHistoryButton(true);
        }

        private function historyButtonOut(event:MouseEvent):void {
            setHistoryButton(false);
        }

        private function toggleChatHistory(event:MouseEvent):void {
            event.stopImmediatePropagation();
            chatHistoryOpen = !chatHistoryOpen;
            setHistoryButton(false);
            chatHistoryBody.visible = chatHistoryOpen;
            for each (var line:TextField in chatHistoryFields) line.visible = chatHistoryOpen && line.length > 0;
        }

        private function historySlot(slot:int):Rectangle {
            var y:Number = historyTop+historyPadding+slot*historyLineHeight;
            // The lower edge of a text line is the narrowest cross-section
            // underneath it. Both sides retain six pixels inside the border.
            var t:Number = (y+historyFieldHeight-historyTop)/(historyBottom-historyTop);
            var left:Number = -64.1+14.95*t+historyPadding;
            var right:Number = 214.85-13.1*t-historyPadding;
            return new Rectangle(left,y,right-left,historyFieldHeight);
        }

        private function historyFits(text:String, width:Number):Boolean {
            chatHistoryMeasure.text = text;
            return chatHistoryMeasure.textWidth <= width-4;
        }

        private function historyNext(start:int, width:Number):Object {
            var end:int = chatHistoryContent.indexOf("\n",start);
            if (end < 0) end = chatHistoryContent.length;
            var low:int = 0;
            var high:int = end-start;
            while (low < high) {
                var mid:int = (low+high+1)/2;
                if (historyFits(chatHistoryContent.substring(start,start+mid),width)) low=mid;
                else high=mid-1;
            }
            var stop:int = start+Math.max(1,low);
            if (start == end) stop = end;
            if (stop < end) {
                var space:int = chatHistoryContent.lastIndexOf(" ",stop);
                if (space > start) stop = space;
            }
            var next:int = stop;
            while (next < end && chatHistoryContent.charAt(next) == " ") next++;
            if (next == end && next < chatHistoryContent.length) next++;
            return {start:start,end:stop,next:next,text:chatHistoryContent.substring(start,stop)};
        }

        private function historyPrevious(end:int, width:Number):Object {
            if (chatHistoryContent.charAt(end-1) == "\n")
                return {start:end-1,end:end-1,next:end-1,text:""};
            var begin:int = chatHistoryContent.lastIndexOf("\n",end-1)+1;
            var low:int = 0;
            var high:int = end-begin;
            while (low < high) {
                var mid:int = (low+high+1)/2;
                if (historyFits(chatHistoryContent.substring(end-mid,end),width)) low=mid;
                else high=mid-1;
            }
            var start:int = Math.max(begin,end-Math.max(1,low));
            if (start > begin && chatHistoryContent.charAt(start-1) != " ") {
                var space:int = chatHistoryContent.indexOf(" ",start);
                if (space >= start && space < end) start=space+1;
            }
            var previous:int = start;
            while (previous > begin && chatHistoryContent.charAt(previous-1) == " ") previous--;
            if (previous == begin && previous > 0) previous--;
            return {start:start,end:end,next:previous,text:chatHistoryContent.substring(start,end)};
        }

        private function scrollChatHistory(event:MouseEvent):void {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (!chatHistoryOpen || event.delta == 0) return;
            var count:int = Math.max(1,Math.min(3,Math.abs(event.delta)));
            var start:int = chatHistoryAnchor;
            if (event.delta > 0) {
                for (var i:int=0;i<count && start>0;i++) start=int(historyPrevious(start,historySlot(0).width).next);
            } else if (chatHistoryLayout.length > 1) {
                start=int(chatHistoryLayout[Math.min(count,chatHistoryLayout.length-1)].start);
            }
            chatHistoryAnchor=Math.max(0,Math.min(start,chatHistoryLatest));
            renderChatHistory(chatHistoryAnchor >= chatHistoryLatest);
        }

        private function historyTime(row:Object):String {
            var stamp:Number = Number(row.received_at);
            if (isNaN(stamp) || stamp <= 0) return "";
            var date:Date = new Date(stamp);
            var hours:String = String(date.hours);
            var minutes:String = String(date.minutes);
            return "["+(hours.length < 2 ? "0" : "")+hours+":"+(minutes.length < 2 ? "0" : "")+minutes+"] ";
        }

        public function addChatHistory(rows:Array):void {
            if (rows == null || rows.length == 0) return;
            var follow:Boolean = chatHistoryFollow;
            for each (var row:Object in rows) {
                if (chatHistoryRows.length > 0 && Number(row.id) <= Number(chatHistoryRows[chatHistoryRows.length-1].id)) continue;
                chatHistoryRows.push(row);
            }
            while (chatHistoryRows.length > 200) {
                var removed:Object = chatHistoryRows.shift();
                chatHistoryAnchor=Math.max(0,chatHistoryAnchor-(historyTime(removed).length+String(removed.sender).length+2+String(removed.text).length+1));
            }
            var parts:Array=[];
            chatHistoryNames=[];
            chatHistoryTimes=[];
            var offset:int=0;
            for each (row in chatHistoryRows) {
                var clock:String=historyTime(row);
                var text:String=clock+String(row.sender)+": "+String(row.text);
                if (clock.length > 0) chatHistoryTimes.push({start:offset,end:offset+clock.length-1});
                chatHistoryNames.push({start:offset+clock.length,end:offset+clock.length+String(row.sender).length+1});
                offset+=text.length+1;
                parts.push(text);
            }
            chatHistoryContent=parts.join("\n");
            renderChatHistory(follow);
        }

        private function renderChatHistory(follow:Boolean):void {
            if (chatHistoryMeasure == null) return;
            var latest:Array=[];
            var cursor:int=chatHistoryContent.length;
            for (var i:int=historySlots-1;i>=0 && cursor>0;i--) {
                var row:Object=historyPrevious(cursor,historySlot(i).width);
                row.slot=i;
                latest.unshift(row);
                cursor=int(row.next);
            }
            chatHistoryLatest=latest.length==0 ? 0 : int(latest[0].start);
            if (cursor == 0 && latest.length < historySlots) chatHistoryLatest=0;
            chatHistoryFollow=follow;
            if (follow) chatHistoryAnchor=chatHistoryLatest;
            chatHistoryLayout=[];
            if (follow && latest.length == historySlots) chatHistoryLayout=latest;
            else {
                cursor=chatHistoryAnchor;
                for (i=0;i<historySlots && cursor<chatHistoryContent.length;i++) {
                    row=historyNext(cursor,historySlot(i).width);
                    row.slot=i;
                    chatHistoryLayout.push(row);
                    cursor=int(row.next);
                }
            }
            for each (var field:TextField in chatHistoryFields) {field.text="";field.visible=false;}
            for each (row in chatHistoryLayout) {
                var bounds:Rectangle=historySlot(int(row.slot));
                field=chatHistoryFields[int(row.slot)];
                field.x=bounds.x;field.y=bounds.y;
                field.width=bounds.width;field.height=bounds.height;
                field.defaultTextFormat=chatHistoryFormat;
                field.text=String(row.text);
                field.visible=chatHistoryOpen && field.length > 0;
                for each (var timeRange:Object in chatHistoryTimes) {
                    var timeStart:int=Math.max(int(row.start),int(timeRange.start));
                    var timeEnd:int=Math.min(int(row.end),int(timeRange.end));
                    if (timeEnd > timeStart) {
                        var timeFormat:TextFormat=new TextFormat();
                        timeFormat.color=0xbfc8b8;
                        field.setTextFormat(timeFormat,timeStart-int(row.start),timeEnd-int(row.start));
                    }
                }
                for each (var name:Object in chatHistoryNames) {
                    var begin:int=Math.max(int(row.start),int(name.start));
                    var end:int=Math.min(int(row.end),int(name.end));
                    if (end>begin) {
                        var format:TextFormat=new TextFormat();
                        format.color=0xd8efa7;
                        field.setTextFormat(format,begin-int(row.start),end-int(row.start));
                    }
                }
            }
        }

        private function historyRangeColor(field:TextField, row:Object, ranges:Array):uint {
            for each (var range:Object in ranges) {
                var begin:int=Math.max(int(row.start),int(range.start));
                if (Math.min(int(row.end),int(range.end)) > begin)
                    return uint(field.getTextFormat(begin-int(row.start),begin-int(row.start)+1).color);
            }
            return 0;
        }

        public function getChatHistoryInfo():Object {
            var button:Rectangle = chatHistoryHit == null ? new Rectangle() : chatHistoryHit.getBounds(this);
            var body:Rectangle = chatHistoryBody == null ? new Rectangle() : chatHistoryBody.getBounds(this);
            var bar:Rectangle = chatHistoryBar == null ? new Rectangle() : chatHistoryBar.getBounds(this);
            var upper:Boolean = false;
            var lower:Boolean = false;
            if (chatHistoryButton != null) for (var i:int=0;i<chatHistoryButton.numChildren;i++) {
                var child:DisplayObject=chatHistoryButton.getChildAt(i);
                if (!(child is Shape) || !child.visible) continue;
                var art:Rectangle=child.getBounds(chatHistoryButton);
                if (art.width > 55 && art.width < 57 && art.height > 12 && art.height < 14) {
                    if (art.y < 0) upper=true;
                    else lower=true;
                }
            }
            var lines:Array=[];
            for each (var row:Object in chatHistoryLayout) {
                var field:TextField=chatHistoryFields[int(row.slot)];
                var bounds:Rectangle=field.getBounds(this);
                lines.push({text:field.text,x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
                    textWidth:field.textWidth,textHeight:field.textHeight,slot:row.slot,
                    start:row.start,end:row.end,nameColor:historyRangeColor(field,row,chatHistoryNames),
                    timeColor:historyRangeColor(field,row,chatHistoryTimes),
                    color:field.text.length==0 ? 0 : field.getTextFormat(0,1).color});
            }
            return {ready:chatHistoryPanel != null,error:chatHistoryError,open:chatHistoryOpen,
                count:chatHistoryRows.length,rows:chatHistoryRows,text:chatHistoryContent,
                scroll:chatHistoryAnchor+1,maxScroll:chatHistoryLatest+1,lines:lines,
                font:chatHistoryFormat == null ? "" : chatHistoryFormat.font,
                embedded:chatHistoryMeasure != null && chatHistoryMeasure.embedFonts,
                upperButtonVisible:upper,lowerButtonVisible:lower,
                buttonFrame:chatHistoryButton == null ? 0 : chatHistoryButton.currentFrame,
                bar:{x:bar.x,y:bar.y,width:bar.width,height:bar.height},
                fillAlpha:chatHistoryFillAlpha,body:{x:body.x,y:body.y,width:body.width,height:body.height},
                x:button.x,y:button.y,width:button.width,height:button.height};
        }

        private var roomAudioManager:Object;
        private var roomAudioMuted:Boolean = false;
        private var roomAudioCompletions:int = 0;
        private var roomAudioQueueCompletions:int = 0;
        private var roomAudioRestarts:int = 0;
        private var miniWorldMusicPaused:Boolean = false;

        private function originalSoundManager():Object {
            if (roomAudioManager == null && ApplicationDomain.currentDomain.hasDefinition("worlds4u.common.SoundManager")) {
                var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.common.SoundManager") as Class;
                roomAudioManager = Object(cls).getInstance();
                roomAudioManager.addEventListener(Event.SOUND_COMPLETE,onRoomAudioComplete);
                roomAudioManager.addEventListener(Event.COMPLETE,onRoomAudioQueueComplete);
            }
            return roomAudioManager;
        }

        private function onRoomAudioQueueComplete(event:Event):void {
            roomAudioQueueCompletions++;
        }

        private function onRoomAudioComplete(event:Event):void {
            roomAudioCompletions++;
        }

        private function updateRoomAudio():void {
            var muted:Boolean = SoundMixer.soundTransform.volume == 0;
            var manager:Object = originalSoundManager();
            // The original manager starts a channel at zero volume in a muted
            // room. Its setMute(false) changes only the mixer, so restart that
            // background through its public API when the original button unmutes.
            if (roomAudioMuted && !muted && miniLayer == null && manager != null && manager.hasSound("BackSoundKey",false)) {
                manager.playAsBackGround("BackSoundKey");
                roomAudioRestarts++;
            }
            roomAudioMuted = muted;
        }

        public function getRoomAudioInfo():Object {
            var manager:Object = originalSoundManager();
            var present:Boolean = manager != null && manager.hasSound("BackSoundKey",false);
            var info:Object = {room:activeRoomKey,loaded:present,muted:SoundMixer.soundTransform.volume == 0,
                mixerVolume:SoundMixer.soundTransform.volume,suspended:miniWorldMusicPaused,
                completions:roomAudioCompletions,queueCompletions:roomAudioQueueCompletions,restarts:roomAudioRestarts};
            if (present) {
                var element:Object = manager.getSoundElement("BackSoundKey");
                info.url = element.request.url;
                info.bytesLoaded = element.soundObject.bytesLoaded;
                info.bytesTotal = element.soundObject.bytesTotal;
                info.length = element.soundObject.length;
            }
            var button:DisplayObject = findNamed(mainClip,"btnMute",0);
            if (button != null) {
                var bounds:Rectangle = button.getBounds(this);
                info.muteButton = {x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height};
            }
            return info;
        }

        public function getWorldPanelInfo():Object {
            var controls:DisplayObject = findNamed(mainClip,"mcControlButtons",0);
            if (controls == null) return null;
            var field:TextField = findNamed(findNamed(controls,"mcChat",0),"txtSpeak",0) as TextField;
            var dance:DisplayObject = findNamed(controls,"mcDanceMove",0);
            var bounds:Rectangle = field == null ? new Rectangle() : field.getBounds(this);
            return {text:field == null ? "" : field.text,
                x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
                textWidth:field == null ? 0 : field.textWidth,
                scrollH:field == null ? 0 : field.scrollH,
                maxScrollH:field == null ? 0 : field.maxScrollH,
                contentScrollH:field == null ? 0 : Math.max(0,Math.ceil(inputCaretX(field,field.length)-bounds.width+4)),
                caretRightGap:field == null ? 0 : field.getBounds(field).width-inputCaretX(field,field.caretIndex)+field.scrollH,
                caret:field == null ? 0 : field.caretIndex,
                multiline:field != null && field.multiline,
                wordWrap:field != null && field.wordWrap,
                defaultAlign:field == null ? "" : field.defaultTextFormat.align,
                align:field == null ? "" : field.getTextFormat().align,
                danceVisible:dance != null && dance.visible};
        }

        public function getChatMenuItems():Array {
            var result:Array = [];
            collectChatMenuItems(mainClip,result);
            return result;
        }

        private function collectChatMenuItems(node:DisplayObject, result:Array):void {
            if (node == null || !node.visible) return;
            if (getQualifiedClassName(node) == "worlds4u.common.uiControls.menus::MenuItem") {
                var item:Object = Object(node).curr_item;
                var bounds:Rectangle = item.mcHit.getBounds(this);
                result.push({text:collectText(item),x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height});
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) collectChatMenuItems(holder.getChildAt(i),result);
        }

        private function worldChat():DisplayObjectContainer {
            if (mainClip == null || worldAvatar == null || lastState.indexOf("world:") != 0) return null;
            var controls:DisplayObject = findNamed(mainClip, "mcControlButtons", 0);
            return findNamed(controls, "mcChat", 0) as DisplayObjectContainer;
        }

        private function consumeChatCommand(event:Event, chat:DisplayObjectContainer):void {
            var field:TextField = findNamed(chat, "txtSpeak", 0) as TextField;
            if (field == null) return;
            var command:String = field.text.replace(/^\s+|\s+$/g, "").toLowerCase();
            var single:Boolean = command.length == 1;
            if (command != "" && command != "/exit" && command != "/help" && !single) return;
            var message:String = field.text.replace(/^\s+|\s+$/g, "");
            // The original ControlPanel treats an empty line as forbidden
            // text. Consume it before its Enter/button handler validates it.
            event.preventDefault();
            event.stopImmediatePropagation();
            field.text = "";
            if (single) ExternalInterface.call("onMogobePublicChat", message);
            else if (command != "") ExternalInterface.call("onMogobeChatCommand", command.substr(1));
        }

        private function worldChatKey(event:KeyboardEvent):void {
            if (event.keyCode == 116 && mainClip != null && worldAvatar != null) {
                event.preventDefault();
                event.stopImmediatePropagation();
                ExternalInterface.call("onMogobeReconnect");
                return;
            }
            if (event.keyCode != 13) return;
            var chat:DisplayObjectContainer = worldChat();
            if (chat != null && event.target == findNamed(chat, "txtSpeak", 0)) consumeChatCommand(event, chat);
        }

        private function worldChatClick(event:MouseEvent):void {
            var chat:DisplayObjectContainer = worldChat();
            if (chat == null) return;
            var send:DisplayObject = findNamed(chat, "btnSend", 0);
            if (send == null) return;
            var target:DisplayObject = event.target as DisplayObject;
            while (target != null && target != chat) {
                if (target == send) {
                    consumeChatCommand(event, chat);
                    return;
                }
                target = target.parent;
            }
        }

        private function findNamed(node:DisplayObject, name:String, depth:int):DisplayObject {
            if (node == null || depth > 12) return null;
            if (node.name == name) return node;
            var container:DisplayObjectContainer = node as DisplayObjectContainer;
            if (container != null) {
                for (var i:int = 0; i < container.numChildren; i++) {
                    var found:DisplayObject = findNamed(container.getChildAt(i), name, depth + 1);
                    if (found != null) return found;
                }
            }
            return null;
        }

        public function getLoginControlBounds(name:String):Object {
            var control:DisplayObject = findNamed(gameLoader, name, 0);
            if (control == null) return null;
            var bounds:Rectangle = control.getBounds(this);
            var clip:MovieClip = control as MovieClip;
            var enabled:Boolean = control.visible && control.mouseEnabled;
            if (clip != null) enabled = enabled && clip.buttonMode && clip.currentLabel != "GREYOUT" && clip.hasEventListener(MouseEvent.CLICK);
            return {x:bounds.x, y:bounds.y, width:bounds.width, height:bounds.height, enabled:enabled};
        }

        public function getSavedAvatarInfo():Array {
            var result:Array=[];
            if (currentLogin==null || loginKind!="saved") return result;
            var names:Array=["mcBigPreviewHolderInst","mcSmallPreviewHolderInst1","mcSmallPreviewHolderInst2","mcSmallPreviewHolderInst3","mcSmallPreviewHolderInst4"];
            for each(var key:String in names) {
                var holder:DisplayObject=findNamed(currentLogin,key,0);
                if(holder==null) continue;
                var label:TextField=findNamed(holder,"txtNameSmall",0) as TextField;
                var clothing:Array=[];collectOutfitClips(holder,clothing);
                result.push({holder:key,username:label==null?"":label.text,clothing:clothing});
            }
            return result;
        }

        private function inspectRemembered():void {
            if (cookieManager == null) return;
            var data:Object = cookieManager.getObjectData("loginInfo");
            var names:Array = [];
            for (var i:int = 0; i < 6; i++) {
                if (data["userName" + i] == null) break;
                names.push(String(data["userName" + i]).toLowerCase());
            }
            var signature:String = names.join("|");
            if (signature != rememberedNames) {
                rememberedNames = signature;
                ExternalInterface.call("onMogobeRememberedAccounts", names);
            }
        }

        private function inspectLoginView():void {
            if (currentLogin != null && loginKind == "saved" && currentLogin != laidOutLogin) {
                layoutSavedPicker();
                laidOutLogin = currentLogin;
            }
            if (currentLogin != null && currentLogin != hookedLogin) {
                hookedLogin = currentLogin;
                currentLogin.addEventListener(Event.COMPLETE, onLoginRequested, false, 100);
            }
            if (currentLogin != null && loginKind != "servers" && registrationUser != "") {
                var info:Object = Object(currentLogin).loginInfo;
                info.userName = registrationUser;
                info.password = "__MOGOBE_CURRENT_SESSION__";
                info.saveUserName = true;
                info.savePassword = false;
                info.lang = 5;
                registrationUser = "";
                // Use the original login-to-server-list flow with the existing
                // HttpOnly session. No registration password enters this SWF.
                currentLogin.dispatchEvent(new Event(Event.COMPLETE));
            }
            var selected:String = "";
            var names:Array = [];
            if (currentLogin != null) {
                var holder:DisplayObjectContainer = findNamed(currentLogin, "mcBigPreviewHolderInst", 0) as DisplayObjectContainer;
                var name:TextField;
                if (holder != null) {
                    name = findNamed(holder, "txtNameSmall", 0) as TextField;
                    if (name != null) selected = showDisplayName(name);
                }
                for (var i:int = 1; i <= 4; i++) {
                    holder = findNamed(currentLogin, "mcSmallPreviewHolderInst" + i, 0) as DisplayObjectContainer;
                    if (holder != null) {
                        name = findNamed(holder, "txtNameSmall", 0) as TextField;
                        if (name != null) {
                            var displayName:String = showDisplayName(name);
                            if (displayName != "") names.push(displayName);
                        }
                    }
                }
            }
            var signature:String = loginKind + ":" + names.join("|") + ":" + selected;
            if (signature != lastLoginView) {
                lastLoginView = signature;
                ExternalInterface.call("onMogobeLoginView", loginKind, names, selected);
            }
        }

        private function showDisplayName(source:TextField):String {
            var canonical:Object = displayNames["$" + source.text.toLowerCase()];
            var value:String = canonical == null ? source.text : String(canonical);
            var label:TextField = source.parent.getChildByName("mogobeDisplayName") as TextField;
            if (label == null) {
                label = new TextField();
                label.name = "mogobeDisplayName";
                label.mouseEnabled = false;
                label.selectable = false;
                source.parent.addChild(label);
            }
            // Original handlers compare these names case-sensitively when
            // removing saved users. Keep their internal key and render the
            // server's spelling in the same place with the original formatting.
            var format:TextFormat = source.getTextFormat();
            format.align = TextFormatAlign.CENTER;
            format.leftMargin = 0;
            format.rightMargin = 0;
            format.indent = 0;
            label.defaultTextFormat = format;
            label.embedFonts = source.embedFonts;
            label.antiAliasType = source.antiAliasType;
            label.gridFitType = source.gridFitType;
            var localBounds:Rectangle = source.getBounds(source);
            label.transform.matrix = new Matrix();
            label.width = localBounds.width;
            label.height = localBounds.height;
            var placement:Matrix = source.transform.matrix.clone();
            placement.tx += placement.a * localBounds.x + placement.c * localBounds.y;
            placement.ty += placement.b * localBounds.x + placement.d * localBounds.y;
            label.transform.matrix = placement;
            label.filters = source.filters;
            label.text = value;
            label.setTextFormat(format);
            label.visible = source.visible && value != "";
            source.alpha = 0;
            return value;
        }

        private function layoutSavedPicker():void {
            var holders:Array = [];
            var positions:Array = [];
            for (var i:int = 1; i <= 4; i++) {
                var holder:DisplayObject = findNamed(currentLogin, "mcSmallPreviewHolderInst" + i, 0);
                if (holder == null) return;
                holders.push(holder);
                positions.push(holder.x);
            }
            // Keep the original data/index mapping and move whole holders into
            // left-to-right order. Text and avatars retain their original scale.
            positions.sort(Array.NUMERIC);
            for (i = 0; i < holders.length; i++) holders[i].x = positions[i];
            var previous:DisplayObject = findNamed(currentLogin, "btnLeftI", 0);
            var next:DisplayObject = findNamed(currentLogin, "btnRightI", 0);
            if (previous == null || next == null) return;
            var previousBounds:Rectangle = previous.getBounds(previous.parent);
            var nextBounds:Rectangle = next.getBounds(next.parent);
            var previousCenter:Number = previousBounds.x + previousBounds.width / 2;
            var nextCenter:Number = nextBounds.x + nextBounds.width / 2;
            if (previousCenter > nextCenter) {
                previous.scaleX = -previous.scaleX;
                next.scaleX = -next.scaleX;
                previousBounds = previous.getBounds(previous.parent);
                nextBounds = next.getBounds(next.parent);
                previous.x += nextCenter - previousBounds.x - previousBounds.width / 2;
                next.x += previousCenter - nextBounds.x - nextBounds.width / 2;
            }
        }

        private function findMain(node:DisplayObject, depth:int):void {
            if ((node != gameLoader && !node.visible) || depth > 8) return;
            var type:String = getQualifiedClassName(node);
            if (type == "Main") {
                mainClip = node as DisplayObjectContainer;
                return;
            }
            if (type == "mogobe.login::LoginScreen" || type == "mogobe.serversList::ServersList") {
                hasLobby = true;
                if (type == "mogobe.login::LoginScreen") {
                    currentLogin = node as DisplayObjectContainer;
                    loginKind = "single";
                    for (var k:int = 0; k < currentLogin.numChildren; k++) {
                        if (getQualifiedClassName(currentLogin.getChildAt(k)) == "mogobe.login::LoginScreenMulti") loginKind = "saved";
                    }
                } else {
                    loginKind = "servers";
                    if (node != hookedServers) {
                        hookedServers = node as DisplayObjectContainer;
                        hookedServers.addEventListener(Event.SELECT, onWorldSelected, false, 100);
                    }
                }
                return;
            }
            var container:DisplayObjectContainer = node as DisplayObjectContainer;
            if (container != null) {
                for (var i:int = 0; i < container.numChildren; i++) {
                    findMain(container.getChildAt(i), depth + 1);
                    if (mainClip != null) return;
                }
            }
        }

        private var miniLayer:Sprite;
        private var miniLoader:Loader;
        private var miniGraphics:Loader;
        private var miniManager:Loader;
        private var miniResult:Object;
        private var miniResultView:MovieClip;
        private var miniResultShade:DisplayObject;
        private var miniFrame:MovieClip;
        private var miniRoot:Object;
        private var miniData:Object;
        private var miniReady:Boolean = false;
        private var miniFinishing:Boolean = false;
        private var miniFrameRate:Number = 24;
        private var miniExit:Object;
        private var miniHelp:Object;
        private var miniHelpView:MovieClip;
        private var miniHelpBack:Object;
        private var miniDisposed:Boolean = false;

        public function openMinigame(data:Object):Boolean {
            if (miniLayer != null || mainClip == null || worldAvatar == null || currentPopup() != null) return false;
            if (data == null || data.key != "goldfishing" || data.swf != "/Swf/Games/GoldFishing.swf") return false;
            miniData = data;
            miniReady = false;
            miniFinishing = false;
            miniDisposed = false;
            miniFrameRate = stage.frameRate;
            miniLayer = new Sprite();
            miniLayer.scrollRect = new Rectangle(0,0,768,480);
            addChild(miniLayer);
            var manager:Object = originalSoundManager();
            miniWorldMusicPaused = manager != null && manager.hasSound("BackSoundKey",false);
            if (miniWorldMusicPaused) manager.stopBackGround();
            miniGraphics = new Loader();
            miniGraphics.contentLoaderInfo.addEventListener(Event.COMPLETE, miniGraphicsLoaded);
            miniGraphics.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, miniLoadFailed);
            miniGraphics.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, miniLoadFailed);
            miniGraphics.load(new URLRequest("/Swf/Assets/Games/ExternalGamesScreens.swf"),
                new LoaderContext(false,new ApplicationDomain(ApplicationDomain.currentDomain)));
            showOriginalLoading(true);
            setChildIndex(originalPreloader,numChildren-1);
            return true;
        }

        private function miniGraphicsLoaded(event:Event):void {
            if (miniLayer == null) return;
            try {
                var frameClass:Class = miniGraphics.contentLoaderInfo.applicationDomain.getDefinition("mlArcadeFrame0") as Class;
                miniFrame = new frameClass() as MovieClip;
                miniFrame.gotoAndStop(1);
                miniLayer.addChild(miniFrame);
                var buttonClass:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.common.uiControls.ButtonSound") as Class;
                miniExit = new buttonClass(miniFrame.btnExit,"Выход");
                miniHelp = new buttonClass(miniFrame.btnHelp,"Помощь");
                miniExit.addEventListener(MouseEvent.CLICK,miniExitClicked);
                miniHelp.addEventListener(MouseEvent.CLICK,miniHelpClicked);
                // Load the unstarted original manager as a library for its GameOver.
                miniManager = new Loader();
                miniManager.contentLoaderInfo.addEventListener(Event.COMPLETE, miniManagerLoaded);
                miniManager.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, miniLoadFailed);
                miniManager.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, miniLoadFailed);
                miniManager.load(new URLRequest("/Swf/Apps/ExternalGameManager.swf"),
                    new LoaderContext(false,new ApplicationDomain(ApplicationDomain.currentDomain)));
            } catch (error:Error) {
                miniLoadFailed();
            }
        }

        private function miniManagerLoaded(event:Event):void {
            if (miniLayer == null) return;
            try {
                miniLoader = new Loader();
                miniLoader.contentLoaderInfo.addEventListener(Event.COMPLETE, miniGameLoaded);
                miniLoader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, miniLoadFailed);
                miniLoader.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, miniLoadFailed);
                miniFrame.mcGameHolder.addChild(miniLoader);
                miniLoader.load(new URLRequest(String(miniData.swf)),
                    new LoaderContext(false,new ApplicationDomain(ApplicationDomain.currentDomain)));
            } catch (error:Error) {
                miniLoadFailed();
            }
        }

        private function miniGameLoaded(event:Event):void {
            if (miniLayer == null) return;
            try {
                miniRoot = miniLoader.content;
                miniRoot.start(miniData.player,miniLayer);
                miniRoot.addEventListener("GAME_EVENT",miniGameFinished);
                miniReady = true;
                stage.frameRate = 15;
                stage.focus = miniLoader;
                showOriginalLoading(false);
                ExternalInterface.call("onMogobeMinigameReady",String(miniData.id));
            } catch (error:Error) {
                miniLoadFailed();
            }
        }

        private function miniLoadFailed(event:Event = null):void {
            if (miniData == null || miniFinishing) return;
            miniFinishing = true;
            showOriginalLoading(false);
            ExternalInterface.call("onMogobeMinigameFinished",String(miniData.id),0,false,"Не удалось загрузить рыбалку.");
        }

        private function miniGameFinished(event:Event):void {
            if (miniData == null || miniFinishing) return;
            miniFinishing = true;
            miniDisposed = true;
            miniLayer.mouseChildren = false;
            miniLayer.mouseEnabled = false;
            var score:Number = Number(Object(event).score);
            ExternalInterface.call("onMogobeMinigameFinished",String(miniData.id),
                isFinite(score) ? Math.max(0,Math.floor(score)) : 0,true,"");
        }

        private function miniExitClicked(event:Event):void {
            if (miniData == null || miniFinishing) return;
            var score:int = miniCurrentScore();
            miniFinishing = true;
            if (miniRoot != null && !miniDisposed) {
                miniRoot.removeEventListener("GAME_EVENT",miniGameFinished);
                try { miniRoot.dispose(miniLayer); } catch (error:Error) {}
                miniDisposed = true;
            }
            ExternalInterface.call("onMogobeMinigameFinished",String(miniData.id),score,false,"");
        }

        public function showMinigameResult(data:Object):Boolean {
            if (miniData == null || data == null || data.id != miniData.id || miniResult != null) return false;
            try {
                closeMiniHelp();
                var resultClass:Class = miniManager.contentLoaderInfo.applicationDomain.getDefinition("worlds4u.ExternalGameManager.GameOver") as Class;
                miniResult = new resultClass(miniGraphics,int(data.score),int(data.coins_awarded),false);
                miniResultView = miniResult.BaseView as MovieClip;
                var popups:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.view.popups.PopupsManeger") as Class;
                miniResultShade = Object(popups).createDisableScreen();
                miniLayer.addChild(miniResultShade);
                miniLayer.addChild(miniResultView);
                // The leaderboard service is not implemented; keep its original disabled state.
                miniResultView.btnTopTen.gotoAndStop("GREYOUT");
                miniResultView.btnTopTen.mouseEnabled = false;
                miniResultView.btnTopTen.mouseChildren = false;
                miniResultView.btnTopTen.buttonMode = false;
                miniResult.addEventListener("Exit",miniResultClosed);
                miniLayer.mouseChildren = true;
                miniLayer.mouseEnabled = true;
                stage.frameRate = miniFrameRate;
                return true;
            } catch (error:Error) {
                return false;
            }
        }

        private function miniResultClosed(event:Event = null):void {
            if (miniResult == null || miniData == null) return;
            var id:String = String(miniData.id);
            closeMinigame();
            ExternalInterface.call("onMogobeMinigameResultClosed",id);
        }

        private function miniCurrentGame():Object {
            var root:DisplayObjectContainer = miniRoot as DisplayObjectContainer;
            if (root != null) for (var i:int=0;i<root.numChildren;i++) {
                var game:DisplayObject = root.getChildAt(i);
                if (getQualifiedClassName(game) == "com.novelgames.flashgames.goldfishing::Game") return game;
            }
            return null;
        }

        private function miniCurrentScore():int {
            var game:Object = miniCurrentGame();
            return game == null ? 0 : Math.max(0,int(game.Score));
        }

        private function miniHelpClicked(event:Event):void {
            if (miniData == null || miniHelpView != null || miniFinishing) return;
            var helpClass:Class = miniGraphics.contentLoaderInfo.applicationDomain.getDefinition("mlHelp") as Class;
            miniHelpView = new helpClass() as MovieClip;
            var language:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.LanguageManager") as Class;
            var font:Class = ApplicationDomain.currentDomain.getDefinition("FontClass") as Class;
            var text:String = Object(language).getInstance().getMessage(1,"GoldFishing");
            miniHelpView.txtHelp = Object(font).getInstance().addText(miniHelpView.txtHelp,text,60,Object(font).FONT_ARIAL,"left");
            miniHelpView.mcPrev.visible = false;
            miniHelpView.mcNext.visible = false;
            var button:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.common.uiControls.ButtonSound") as Class;
            miniHelpBack = new button(miniHelpView.mcExitGame,Object(language).getInstance().getMessage(16,"GameManager"));
            miniHelpBack.addEventListener(MouseEvent.CLICK,closeMiniHelp);
            miniLayer.addChild(miniHelpView);
            var timer:Class = miniLoader.contentLoaderInfo.applicationDomain.getDefinition("com.novelgames.flashgames.common.NewTimer") as Class;
            Object(timer).pause();
        }

        public function closeMiniHelp(event:Event = null):void {
            if (miniHelpView == null) return;
            if (miniHelpBack != null) miniHelpBack.removeAllEventListener();
            miniLayer.removeChild(miniHelpView);
            miniHelpView = null;miniHelpBack = null;
            var timer:Class = miniLoader.contentLoaderInfo.applicationDomain.getDefinition("com.novelgames.flashgames.common.NewTimer") as Class;
            Object(timer).unpause();
        }

        private function miniKey(event:KeyboardEvent):void {
            if (miniLayer == null) return;
            if (event.keyCode == 116) {
                event.preventDefault();event.stopImmediatePropagation();
                ExternalInterface.call("onMogobeReconnect");
            } else if (event.keyCode == 27) {
                event.preventDefault();event.stopImmediatePropagation();
                if (miniHelpView != null) closeMiniHelp();
                else if (miniResult != null) miniResultClosed();
                else miniExitClicked(event);
            }
        }

        public function closeMinigame():void {
            if (miniLayer == null) return;
            miniFinishing = true;
            closeMiniHelp();
            if (miniRoot != null && !miniDisposed) {
                miniRoot.removeEventListener("GAME_EVENT",miniGameFinished);
                try { miniRoot.dispose(miniLayer); } catch (error:Error) {}
            }
            if (miniResult != null) {
                miniResult.removeEventListener("Exit",miniResultClosed);
                miniResult.disableEvents();
            }
            miniResult = null;miniResultView = null;miniResultShade = null;
            if (miniExit != null) miniExit.removeAllEventListener();
            if (miniHelp != null) miniHelp.removeAllEventListener();
            if (miniLoader != null) {
                miniLoader.contentLoaderInfo.removeEventListener(Event.COMPLETE,miniGameLoaded);
                miniLoader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,miniLoadFailed);
                miniLoader.contentLoaderInfo.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,miniLoadFailed);
                try { miniLoader.unloadAndStop(true); } catch (error2:Error) {}
            }
            if (miniManager != null) {
                miniManager.contentLoaderInfo.removeEventListener(Event.COMPLETE,miniManagerLoaded);
                miniManager.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,miniLoadFailed);
                miniManager.contentLoaderInfo.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,miniLoadFailed);
                try { miniManager.unloadAndStop(true); } catch (managerError:Error) {}
            }
            if (miniGraphics != null) {
                miniGraphics.contentLoaderInfo.removeEventListener(Event.COMPLETE,miniGraphicsLoaded);
                miniGraphics.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,miniLoadFailed);
                miniGraphics.contentLoaderInfo.removeEventListener(SecurityErrorEvent.SECURITY_ERROR,miniLoadFailed);
                try { miniGraphics.unloadAndStop(true); } catch (error3:Error) {}
            }
            removeChild(miniLayer);
            miniLayer = null;miniLoader = null;miniGraphics = null;miniManager = null;miniFrame = null;
            miniRoot = null;miniData = null;miniExit = null;miniHelp = null;miniReady = false;
            stage.frameRate = miniFrameRate;
            stage.focus = gameLoader;
            showOriginalLoading(false);
            var manager:Object = originalSoundManager();
            if (miniWorldMusicPaused && manager != null && manager.hasSound("BackSoundKey",false)) manager.playAsBackGround("BackSoundKey");
            miniWorldMusicPaused = false;
        }

        public function getMinigameInfo():Object {
            if (miniData == null) return null;
            var info:Object = {id:miniData.id,key:miniData.key,ready:miniReady,finishing:miniFinishing,
                avatarColor:miniData.player.avatarColor,frameRate:stage.frameRate,
                score:miniCurrentScore(),helpOpen:miniHelpView != null};
            var game:Object = miniCurrentGame();
            if (game != null && !miniDisposed) {
                info.time = int(game.time);
                info.hookAngle = Number(game.hook.angle);
                info.hookX = Number(game.hook.x);info.hookY = Number(game.hook.y);
                info.targets = [];
                for (var i:int=0;i<game.thingsHolder.numChildren;i++) {
                    var thing:Object = game.thingsHolder.getChildAt(i);
                    if (thing.visible) info.targets.push({x:thing.x,y:thing.y,value:thing.value});
                }
            }
            if (miniHelpView != null) {
                info.helpText = miniHelpView.txtHelp.text;
                var back:Rectangle = miniHelpView.mcExitGame.getBounds(this);
                info.helpBack = {x:back.x,y:back.y,width:back.width,height:back.height};
            }
            if (miniResultView != null) {
                info.resultClass = getQualifiedClassName(miniResultView);
                info.resultText = collectText(miniResultView);
                info.resultScore = collectText(miniResultView.mcWinnerTXT);
                var resultExit:Rectangle = miniResultView.mcExitGame.getBounds(this);
                info.resultExit = {x:resultExit.x,y:resultExit.y,width:resultExit.width,height:resultExit.height};
            }
            if (miniFrame != null) {
                var exit:Rectangle = miniFrame.btnExit.getBounds(this);
                info.exit = {x:exit.x,y:exit.y,width:exit.width,height:exit.height};
                var help:Rectangle = miniFrame.btnHelp.getBounds(this);
                info.help = {x:help.x,y:help.y,width:help.width,height:help.height};
            }
            return info;
        }


        private function inspectScene(event:Event):void {
            hasLobby = false;
            mainClip = null;
            currentLogin = null;
            loginKind = "";
            findMain(gameLoader, 0);
            updateServerPresence();
            inspectLoginView();
            inspectRemembered();
            var state:String = "loading";
            var room:String = "";
            var panelReady:Boolean = false;
            var avatarReady:Boolean = false;
            worldAvatar = null;
            activeRoomView = null;
            activeRoomKey = "";
            if (mainClip != null) {
                for (var i:int = 0; i < mainClip.numChildren; i++) {
                    var child:DisplayObject = mainClip.getChildAt(i);
                    if (!child.visible) continue;
                    var type:String = getQualifiedClassName(child);
                    if (type == "mlControlPanel") {
                        var buttons:DisplayObject = (child as DisplayObjectContainer).getChildByName("mcControlButtons");
                        panelReady = buttons != null && buttons.visible;
                    }
                    var roomView:DisplayObjectContainer = child as DisplayObjectContainer;
                    var zOrder:DisplayObjectContainer = roomView == null ? null : roomView.getChildByName("mcZOrder") as DisplayObjectContainer;
                    if (type.indexOf("ml") == 0 && zOrder != null && roomView.getChildByName("mcWalkingArea") != null) {
                        prepareRoomView(roomView);
                        room = type.substr(2).toLowerCase();
                        activeRoomView = roomView;
                        activeRoomKey = room;
                        if (zOrder != null) {
                            for (var j:int = 0; j < zOrder.numChildren; j++) {
                                var avatar:DisplayObject = zOrder.getChildAt(j);
                                if (getQualifiedClassName(avatar) == "worlds4u.view.avatar::MyAvatar" && avatar.visible) {
                                    avatarReady = true;
                                    worldAvatar = avatar;
                                    worldAvatar.addEventListener(Event.COMPLETE,beginOriginalShopArrival,false,200);
                                    worldAvatar.addEventListener(Event.COMPLETE,finishOriginalShopArrival,false,-200);
                                    break;
                                }
                            }
                        }
                    }
                }
                if (room != "" && panelReady && avatarReady) state = "world";
            } else if (hasLobby && !worldStarting) {
                state = "lobby";
            }
            refreshFriendsFonts();
            updateFriendTooltip();
            updateProfileCounters();
            if (loginKind == "servers") registrationPending = false;
            if (registrationPending) state = "loading";
            if (miniLayer != null) state = miniReady ? "minigame" : "loading";
            // Suppress input while original Main is building the room/panel.
            gameLoader.mouseChildren = state != "loading" && miniLayer == null;
            gameLoader.mouseEnabled = state != "loading" && miniLayer == null;
            var signature:String = state + ":" + room;
            if (signature != lastState) {
                lastState = signature;
                showOriginalLoading(state == "loading");
                ExternalInterface.call("onMogobeSceneState", state, room, panelReady, avatarReady);
            }
        }
        private var activeRoomView:DisplayObjectContainer;
        private var activeRoomKey:String="";
        private var worldShopRoom:String="";
        private var worldShopPoints:Array=[];
        private var shopPopup:Object;
        private var shopModel:flash.events.EventDispatcher;
        private var shopData:Object;
        private var shopStore:Object;
        private var shopItems:Object={};
        private var shopSelectedItem:int=0;

        public function setWorldShopPoints(data:Object):void {
            worldShopRoom = String(data.room);
            worldShopPoints = data.points as Array;
            if (worldShopPoints == null) worldShopPoints = [];
        }

        public function getWorldShopPoints():Array {
            return worldShopRoom == activeRoomKey ? worldShopPoints : [];
        }

        private function originalShopPointAtAvatar():Object {
            if (activeRoomView == null || worldAvatar == null) return null;
            var feet:flash.geom.Point = Object(worldAvatar).AvatarHitPoint;
            var exits:DisplayObjectContainer = activeRoomView.getChildByName("mcExisPoints") as DisplayObjectContainer;
            if (exits == null) return null;
            if (worldShopRoom == activeRoomKey) for each (var point:Object in worldShopPoints) {
                var region:DisplayObject = exits.getChildByName(String(point.name));
                if (region != null && region.hitTestPoint(feet.x,feet.y,true)) return point;
            }
            // Arrival handling must not wait for an HTTP point list. Also route
            // disabled/unassigned native shops to a proper unavailable message.
            for (var i:int=0;i<exits.numChildren;i++) {
                region=exits.getChildAt(i);
                var name:String=region.name;
                if (name.indexOf("mcShopPoint_") != 0 && !(activeRoomKey == "bumagsstore" && name == "mcPopupPoint_51")) continue;
                if (region.hitTestPoint(feet.x,feet.y,true)) return {id:activeRoomKey+"."+name,name:name};
            }
            return null;
        }

        public function getWorldShopState():Object {
            var point:Object = originalShopPointAtAvatar();
            return {at:point == null ? null : point.id,windowsCreated:shopWindowsCreated,originalArrivals:nativeShopOpenings,nativeOpenings:nativeShopOpenings};
        }

        private var nativeShopOpenings:int=0;
        private var shopWindowsCreated:int=0;
        private var shopArrivalRegion:DisplayObject;
        private var shopArrivalX:Number;
        private var shopArrivalPoint:Object;

        private function beginOriginalShopArrival(event:Event):void {
            var point:Object=originalShopPointAtAvatar();
            if (point == null || currentPopup() != null) return;
            var exits:DisplayObjectContainer=activeRoomView.getChildByName("mcExisPoints") as DisplayObjectContainer;
            shopArrivalRegion=exits.getChildByName(String(point.name));
            shopArrivalPoint=point;
            shopArrivalX=shopArrivalRegion.x;
            // Keep the original walk-complete/cursor bookkeeping, suppress only
            // the old popup branch during this synchronous event dispatch, then
            // restore the exact shape before requesting the assigned catalog.
            // No placeholder window is constructed or painted first.
            shopArrivalRegion.x += 10000;
        }

        private function finishOriginalShopArrival(event:Event):void {
            if (shopArrivalRegion == null) return;
            shopArrivalRegion.x=shopArrivalX;
            var point:Object=shopArrivalPoint;
            shopArrivalRegion=null;
            shopArrivalPoint=null;
            nativeShopOpenings++;
            ExternalInterface.call("onMogobeWorldShop",String(point.id));
        }

        private function watchOriginalShop():void {
            // Let the original avatar manager walk, stop and open its popup.
            // A floor click or the bounding box of a rotated trigger is not an arrival.
            var popup:Object = currentPopup();
            if (popup == null || popup == shopPopup || (popup.PopupId != 33 && popup.PopupId != 51)) return;
            var point:Object = originalShopPointAtAvatar();
            if (point == null) return;
            nativeShopOpenings++;
            popup.disableEvents();
            popup.dispatchEvent(new Event(Event.CLOSE));
            ExternalInterface.call("onMogobeWorldShop",String(point.id));
        }

        public function openOriginalShop(data:Object):Boolean {
            if (mainClip == null || worldAvatar == null) return false;
            var existing:Object = currentPopup();
            if (existing != null && existing != shopPopup) return false;
            if (shopPopup != null && shopPopup.baseView.stage != null) {
                if (shopData.key == data.key && shopData.kind == data.kind) {
                    refreshOriginalShop(data);
                    return true;
                }
                closeOriginalShop();
            }
            shopData = data;
            shopStore = null;
            shopItems = {};
            shopSelectedItem = 0;
            shopModel = new flash.events.EventDispatcher();
            var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.view.popups.PopupsManeger") as Class;
            shopPopup = Object(cls).getInstance().showPopWithLoad(33,{popupId:data.kind == "clothing" ? 2 : 6},shopModel);
            shopPopup.addEventListener("STORE_DATA_EVT",shopRequest);
            shopPopup.addEventListener("ASK_DATA_EVT",shopRequest);
            shopPopup.addEventListener("BUY_ITEM_EVT",shopRequest);
            shopPopup.addEventListener(Event.CLOSE,shopClosed);
            return true;
        }

        private function shopClosed(event:Event):void {
            shopPopup = null;
            shopModel = null;
            shopData = null;
            shopStore = null;
            shopItems = {};
            shopSelectedItem = 0;
            ExternalInterface.call("onMogobeShopClosed");
        }

        private function shopRequest(event:Event):void {
            if (shopData == null) return;
            var cls:Class;
            if (event.type == "STORE_DATA_EVT") {
                var store:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.data.StoreTO") as Class;
                cls = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.RoomEvent") as Class;
                shopStore = new store(shopData);
                rememberShopItems();
                shopModel.dispatchEvent(new cls("STORE_DATA_EVT",shopStore,"rooms__getStoreData"));
            } else if (event.type == "ASK_DATA_EVT") {
                sendShopUser();
            } else if (event.type == "BUY_ITEM_EVT") {
                var id:int = int(Object(event).Data);
                shopSelectedItem = id;
                var price:int = -1;
                for each (var item:Object in shopData.items) if (int(item.typeId) == id) price = int(item.price);
                ExternalInterface.call("onMogobeShopBuy",shopData.key,id,price);
            }
        }

        private function sendShopUser():void {
            if (shopData == null || shopModel == null) return;
            var userClass:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.data.UserTO") as Class;
            var user:Object = new userClass(int(shopData.user.userId),String(shopData.user.userName),true);
            var values:Array = [];
            for (var key:String in shopData.user) values[key] = shopData.user[key];
            values["mo_1"] = shopData.coins;
            user.Varibales = values;
            var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.AvatarEvent") as Class;
            shopModel.dispatchEvent(new cls("ASK_DATA_EVT","user__getUserTO",user,int(shopData.user.userId)));
        }

        private function rememberShopItems():void {
            shopItems = {};
            for each (var category:Object in shopStore.getCatecories())
                for each (var item:Object in shopStore.getItemsByCategory(category.TypeId))
                    shopItems[String(item.TypeId)] = item;
        }

        private function shopGrid(node:DisplayObject, type:String):Object {
            if (getQualifiedClassName(node) == "worlds4u.common.uiControls.DataGrid::"+type) return node;
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int=0;i<holder.numChildren;i++) {
                var found:Object=shopGrid(holder.getChildAt(i),type);
                if (found != null) return found;
            }
            return null;
        }

        private function sameShopStructure(data:Object):Boolean {
            if (shopStore == null || data.kind != shopData.kind || data.items.length != shopData.items.length || data.categories.length != shopData.categories.length) return false;
            for (var i:int=0;i<data.categories.length;i++)
                if (data.categories[i].typeId != shopData.categories[i].typeId || data.categories[i].name != shopData.categories[i].name) return false;
            for (i=0;i<data.items.length;i++) {
                var a:Object=data.items[i];
                var b:Object=shopData.items[i];
                if (a.typeId != b.typeId || a.sCat != b.sCat || a.pCat != b.pCat || a.mType != b.mType) return false;
            }
            return true;
        }

        public function refreshOriginalShop(data:Object):void {
            if (shopPopup == null || shopData == null || data.key != shopData.key) return;
            if (data.sourcePoint == null) data.sourcePoint = shopData.sourcePoint;
            if (sameShopStructure(data)) {
                // Prices, balance and stock do not replace StoreTO or reset Data.
                // Rebind only the visible eight cells; ButtonDataGrid retains its page.
                var grid:Object=shopGrid(shopPopup.baseView,"ButtonDataGrid");
                var selected:int=grid != null && grid.selected != null ? int(grid.selected.TypeId) : shopSelectedItem;
                for each (var raw:Object in data.items) {
                    var item:Object=shopItems[String(raw.typeId)];
                    if (item != null) { item.Price=int(raw.price);item.InStock=Boolean(raw.inStock); }
                }
                shopData = data;
                if (grid != null) {
                    grid.baind();
                    if (selected>0 && shopItems[String(selected)] != null) grid.select(shopItems[String(selected)]);
                }
            } else {
                shopData = data;
                var store:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.model.data.StoreTO") as Class;
                var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.RoomEvent") as Class;
                shopStore = new store(data);
                rememberShopItems();
                shopModel.dispatchEvent(new cls("STORE_DATA_EVT",shopStore,"rooms__getStoreData"));
            }
            sendShopUser();
        }

        public function finishShopPurchase(success:Boolean):void {
            if (shopModel == null) return;
            var cls:Class = ApplicationDomain.currentDomain.getDefinition("worlds4u.events.AvatarEvent") as Class;
            shopModel.dispatchEvent(new cls("BUY_ITEM_EVT","user__buyItem",{status:success,msgId:-1},-1));
        }

        public function closeOriginalShop():void {
            if (shopPopup == null) return;
            try { shopPopup.disableEvents(); } catch (error:Error) {}
            shopPopup.dispatchEvent(new Event(Event.CLOSE));
        }

        private function countShopGraphics(node:DisplayObject):int {
            var type:String = getQualifiedClassName(node);
            var result:int = type.indexOf("btnItem") == 0 || type.indexOf("mlBigItem") == 0 ? 1 : 0;
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) result += countShopGraphics(holder.getChildAt(i));
            return result;
        }

        private function findShopGraphic(node:DisplayObject, prefix:String):DisplayObject {
            if (getQualifiedClassName(node).indexOf(prefix) == 0) return node;
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) {
                var found:DisplayObject = findShopGraphic(holder.getChildAt(i),prefix);
                if (found != null) return found;
            }
            return null;
        }

        private function shopCells(node:DisplayObject, result:Array):void {
            if (getQualifiedClassName(node) == "worlds4u.common.uiControls.DataGrid::GridCellStore") {
                var data:Object = Object(node).Data;
                var bounds:Rectangle = node.getBounds(this);
                var hit:flash.geom.Point = globalToLocal(node.localToGlobal(new flash.geom.Point(42.85,31.95)));
                var artwork:DisplayObject = findShopGraphic(node,"btnItem");
                var artBounds:Rectangle = artwork == null ? null : artwork.getBounds(node);
                var priceLabel:TextField = DisplayObjectContainer(node).getChildByName("mogobeGridPrice") as TextField;
                var priceBounds:Rectangle = priceLabel == null ? null : priceLabel.getBounds(this);
                result.push({priceVisible:priceLabel != null && priceLabel.visible,priceText:priceLabel == null ? null : priceLabel.text,
                    priceX:priceBounds == null ? 0 : priceBounds.x + priceBounds.width/2,
                    priceY:priceBounds == null ? 0 : priceBounds.y + priceBounds.height/2,
                    art:artBounds == null ? null : {x:artBounds.x,y:artBounds.y,width:artBounds.width,height:artBounds.height},hitX:hit.x,hitY:hit.y,id:int(data.TypeId),price:int(data.Price),available:Boolean(data.InStock),
                    x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height,
                    graphics:countShopGraphics(node)});
            }
            var holder:DisplayObjectContainer = node as DisplayObjectContainer;
            if (holder != null) for (var i:int = 0; i < holder.numChildren; i++) shopCells(holder.getChildAt(i),result);
        }

        public function getShopInfo():Object {
            if (shopPopup == null || shopData == null) return null;
            var cells:Array = [];
            shopCells(shopPopup.baseView,cells);
            var preview:DisplayObject = findNamed(shopPopup.baseView,"mcAvatarBig",0);
            var wornPreview:DisplayObject = preview == null ? null : findShopGraphic(preview,"mlBigItem");
            var panel:DisplayObjectContainer = findNamed(shopPopup.baseView,"mcShop",0) as DisplayObjectContainer;
            var luxury:DisplayObject = panel == null ? null : panel.getChildByName("txtAmount_2");
            var amount:DisplayObject = panel == null ? null : panel.getChildByName("txtAmount_1");
            var tabs:Array = [];
            var categoryCells:Array = [];
            collectShopCategories(shopPopup.baseView,categoryCells);
            for each (var cell:DisplayObject in categoryCells) {
                var center:flash.geom.Point = globalToLocal(cell.localToGlobal(new flash.geom.Point(22.475,18.25)));
                var area:Rectangle = cell.getBounds(this);
                var icon:DisplayObject = findShopGraphic(cell,"btnCat");
                tabs.push({id:int(Object(cell).Data.TypeId),iconVisible:icon != null && icon.visible,
                    hitX:center.x,hitY:center.y,x:area.x,y:area.y,width:area.width,height:area.height});
            }
            var holder:DisplayObjectContainer = findNamed(shopPopup.baseView,"mcBigDisplay",0) as DisplayObjectContainer;
            var selected:DisplayObject = holder == null ? null : holder.getChildByName("selectedItem");
            var previewBounds:Rectangle = selected == null ? null : selected.getBounds(holder);
            var itemGrid:Object=shopGrid(shopPopup.baseView,"ButtonDataGrid");
            var categoryGrid:Object=shopGrid(shopPopup.baseView,"ScrollDataGrid");
            return {sourcePoint:shopData.sourcePoint,selectedItem:itemGrid != null && itemGrid.selected != null ? itemGrid.selected.TypeId : null,selectedCategory:categoryGrid != null && categoryGrid.selected != null ? categoryGrid.selected.TypeId : null,categoryScrollers:countVisibleCategoryScrollers(shopPopup.baseView),tryOn:wornPreview == null ? null : getQualifiedClassName(wornPreview),categories:tabs,preview:previewBounds == null ? null : {x:previewBounds.x,y:previewBounds.y,width:previewBounds.width,height:previewBounds.height},
                luxuryVisible:luxury != null && luxury.visible,coinY:amount == null ? 0 : amount.y,
                key:shopData.key,title:shopData.title,kind:shopData.kind,coins:shopData.coins,
                itemCount:shopData.items.length,items:cells,text:collectText(shopPopup.baseView),
                visible:shopPopup.baseView.stage != null,avatar:preview != null && preview.visible};
        }


    }
}
